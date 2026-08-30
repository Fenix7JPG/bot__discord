"""Repositorio de configuración por servidor y ranking de alianzas.

Incluye la configuracion de economia por servidor (feature 001) con
validacion de rangos y auditoria de cambios.
"""

from datetime import datetime, timezone

from database.database import db

CAMPOS_CONFIG = (
    "welcome_channel_id",
    "ticket_category_id",
    "alliance_channel_id",
    "hunter_role_id",
    "alliance_role_id",
)


def set_config(guild_id: int, campo: str, valor: int) -> None:
    """Guarda un campo de configuración del servidor (upsert)."""
    if campo not in CAMPOS_CONFIG:
        raise ValueError("Campo no permitido: " + str(campo))
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO guild_config (guild_id, {campo}) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {campo} = excluded.{campo}
            """.format(campo=campo),
            (guild_id, valor),
        )


def get_config(guild_id: int, campo: str) -> int | None:
    if campo not in CAMPOS_CONFIG:
        raise ValueError("Campo no permitido: " + str(campo))
    with db.connect() as conn:
        conn.execute(
            "SELECT {campo} FROM guild_config WHERE guild_id = ?".format(campo=campo),
            (guild_id,),
        )
        row = conn.fetchone()
        return row[campo] if row else None


# ---------------------------------------------------------------------------
# Ranking de cazadores de alianzas
# ---------------------------------------------------------------------------

def add_point(guild_id: int, user_id: int) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO alliance_ranking (guild_id, user_id, points)
            VALUES (?, ?, 1)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET points = points + 1
            """,
            (guild_id, user_id),
        )


def get_points(guild_id: int, user_id: int) -> int:
    with db.connect() as conn:
        conn.execute(
            "SELECT points FROM alliance_ranking WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        row = conn.fetchone()
        return row["points"] if row else 0


def get_ranking(guild_id: int, limit: int = 10) -> list[dict]:
    with db.connect() as conn:
        conn.execute(
            """
            SELECT user_id, points FROM alliance_ranking
            WHERE guild_id = ?
            ORDER BY points DESC LIMIT ?
            """,
            (guild_id, limit),
        )
        return conn.fetchall()


def get_position(guild_id: int, user_id: int) -> int | None:
    ranking = get_ranking(guild_id, limit=10_000)
    for i, fila in enumerate(ranking, start=1):
        if fila["user_id"] == user_id:
            return i
    return None


# ---------------------------------------------------------------------------
# Configuracion de economia por servidor (feature 001-dashboard-trabajos)
# ---------------------------------------------------------------------------

ECONOMIA_DEFAULTS = {
    "work_mode": "turnos",
    "minigame": "calculo",
    "turns_per_session": 3,
    "sessions_per_day": 2,
    "health_loss_chance": 35,
    "lucky_chance": 30,
}

# Rangos permitidos por campo numerico (validados antes de escribir)
ECONOMIA_RANGOS = {
    "turns_per_session": (1, 5),
    "sessions_per_day": (1, 10),
    "health_loss_chance": (0, 100),
    "lucky_chance": (0, 100),
}

ECONOMIA_ENUMS = {
    "work_mode": ("turnos", "cooldown"),
    "minigame": ("calculo", "memoria"),
}

# Union de campos editables (numericos + enums)
CAMPOS_ECONOMIA = tuple(ECONOMIA_RANGOS) + tuple(ECONOMIA_ENUMS)


def get_economia(guild_id: int) -> dict:
    """Config de economia del servidor, con defaults si no hay fila."""
    config = dict(ECONOMIA_DEFAULTS)
    with db.connect() as conn:
        conn.execute(
            "SELECT * FROM server_economy_config WHERE guild_id = ?",
            (guild_id,),
        )
        fila = conn.fetchone()
    if fila:
        for campo in CAMPOS_ECONOMIA:
            if fila.get(campo) is not None:
                config[campo] = fila[campo]
    return config


def set_economia(guild_id: int, valores: dict, actor_id: int, actor_name: str) -> list[dict]:
    """Valida y guarda campos de economia (upsert) + auditoria por cambio.

    Devuelve la lista de cambios hechos: [{campo, anterior, nuevo}].
    Lanza ValueError si algun campo es invalido SIN escribir nada.
    """
    actual = get_economia(guild_id)

    # Validar TODO antes de escribir (sin escritura parcial)
    limpios: dict[str, object] = {}
    for campo, valor in valores.items():
        if campo not in CAMPOS_ECONOMIA:
            raise ValueError("Campo de economia no permitido: " + str(campo))
        if campo in ECONOMIA_ENUMS:
            if valor not in ECONOMIA_ENUMS[campo]:
                permitidos = ", ".join(ECONOMIA_ENUMS[campo])
                raise ValueError(
                    campo + " debe ser uno de: " + permitidos
                )
        else:
            minimo, maximo = ECONOMIA_RANGOS[campo]
            try:
                numero = int(valor)
            except (TypeError, ValueError):
                raise ValueError(campo + " debe ser un numero entero")
            if numero < minimo or numero > maximo:
                raise ValueError(
                    campo
                    + " debe estar entre "
                    + str(minimo)
                    + " y "
                    + str(maximo)
                )
            valor = numero
        limpios[campo] = valor

    # Detectar cambios reales y armar auditoria
    fecha = datetime.now(tz=timezone.utc).isoformat()
    cambios: list[dict] = []
    for campo, valor in limpios.items():
        anterior = actual.get(campo)
        if anterior == valor:
            continue
        cambios.append(
            {
                "campo": campo,
                "anterior": anterior,
                "nuevo": valor,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "fecha": fecha,
            }
        )

    if cambios:
        with db.connect() as conn:
            for campo in ECONOMIA_ENUMS:
                if campo in limpios:
                    conn.execute(
                        """
                        INSERT INTO server_economy_config (guild_id, {campo})
                        VALUES (?, ?)
                        ON CONFLICT(guild_id) DO UPDATE SET {campo} = excluded.{campo}
                        """.format(campo=campo),
                        (guild_id, limpios[campo]),
                    )
            for campo in ECONOMIA_RANGOS:
                if campo in limpios:
                    conn.execute(
                        """
                        INSERT INTO server_economy_config (guild_id, {campo})
                        VALUES (?, ?)
                        ON CONFLICT(guild_id) DO UPDATE SET {campo} = excluded.{campo}
                        """.format(campo=campo),
                        (guild_id, limpios[campo]),
                    )
            for cambio in cambios:
                conn.execute(
                    """
                    INSERT INTO config_audit
                        (guild_id, actor_id, actor_name, campo, valor_anterior, valor_nuevo, fecha)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        cambio["actor_id"],
                        cambio["actor_name"],
                        cambio["campo"],
                        "" if cambio["anterior"] is None else str(cambio["anterior"]),
                        str(cambio["nuevo"]),
                        cambio["fecha"],
                    ),
                )
    return cambios


def get_auditoria(guild_id: int, limit: int = 20) -> list[dict]:
    """Ultimos cambios de configuracion del servidor (mas nuevo primero)."""
    with db.connect() as conn:
        conn.execute(
            """
            SELECT guild_id, actor_id, actor_name, campo, valor_anterior, valor_nuevo, fecha
            FROM config_audit
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        return conn.fetchall()


def registrar_cambio(guild_id: int, actor_id, actor_name: str,
                     campo: str, valor_anterior, valor_nuevo) -> None:
    """Inserta un registro de auditoria (lo usan economia y el dashboard)."""
    from datetime import datetime, timezone

    fecha = datetime.now(tz=timezone.utc).isoformat()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO config_audit
                (guild_id, actor_id, actor_name, campo, valor_anterior, valor_nuevo, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                actor_id,
                actor_name,
                campo,
                "" if valor_anterior is None else str(valor_anterior),
                "" if valor_nuevo is None else str(valor_nuevo),
                fecha,
            ),
        )
