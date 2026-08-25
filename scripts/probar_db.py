"""Prueba de conexión con la base de datos configurada.

Uso: python scripts/probar_db.py
Crea las tablas, escribe y lee un dato de prueba.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database.database import db  # noqa: E402


def main():
    print("Modo de base de datos:", db.mode)
    db.setup()
    with db.connect() as conn:
        conn.execute("SELECT COUNT(*) AS n FROM jugadores")
        fila = conn.fetchone()
        print("Tablas OK. Jugadores registrados:", fila["n"])
        conn.execute(
            "INSERT INTO jugadores (user_id) VALUES (?)", (-999,)
        )
    with db.connect() as conn:
        conn.execute("DELETE FROM jugadores WHERE user_id = ?", (-999,))
    print("Lectura y escritura de prueba: OK")


if __name__ == "__main__":
    main()
