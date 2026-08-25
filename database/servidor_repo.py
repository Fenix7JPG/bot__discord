"""Repositorio de configuración por servidor y ranking de alianzas."""

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
