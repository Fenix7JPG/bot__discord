"""Repositorio de jugadores: perfiles del juego (dinero, trabajo, salud).

Un perfil por usuario de Discord, compartido entre servidores.
"""

from database.database import db


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def get_jugador(user_id: int) -> dict | None:
    with db.connect() as conn:
        conn.execute("SELECT * FROM jugadores WHERE user_id = ?", (user_id,))
        return _row_to_dict(conn.fetchone())


def crear_jugador(user_id: int) -> bool:
    """Crea el perfil. Devuelve False si ya existía."""
    if get_jugador(user_id) is not None:
        return False
    with db.connect() as conn:
        conn.execute("INSERT INTO jugadores (user_id) VALUES (?)", (user_id,))
    return True


def actualizar_campo(user_id: int, campo: str, valor) -> None:
    """Actualiza un campo del perfil. Los nombres permitidos están en la lista
    para que nunca se pueda inyectar SQL por el nombre de columna."""
    permitidos = (
        "dinero",
        "experiencia",
        "trabajo",
        "fecha_trabajo",
        "salud",
        "enfermedad",
        "fecha_enfermedad",
        "dia_ultimo_trabajo",
        "sesiones_hoy",
    )
    if campo not in permitidos:
        raise ValueError("Campo no permitido: " + str(campo))
    with db.connect() as conn:
        conn.execute(
            "UPDATE jugadores SET " + campo + " = ? WHERE user_id = ?",
            (valor, user_id),
        )


def actualizar_campos(user_id: int, valores: dict) -> None:
    for campo, valor in valores.items():
        actualizar_campo(user_id, campo, valor)


# ---------------------------------------------------------------------------
# Helpers de negocio usados por varios comandos
# ---------------------------------------------------------------------------

CAMPOS_INICIALES = {
    "dinero": 0,
    "experiencia": 0,
    "trabajo": None,
    "fecha_trabajo": None,
    "salud": 100,
    "enfermedad": None,
    "fecha_enfermedad": None,
    "dia_ultimo_trabajo": None,
    "sesiones_hoy": 0,
}
