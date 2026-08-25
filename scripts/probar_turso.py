"""Verifica que la base Turso remota responde y tiene el esquema.

Uso (con TURSO_AUTH_TOKEN en el entorno o .env):
    python scripts/probar_turso.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings  # noqa: E402
from database.database import db  # noqa: E402


def main():
    if not settings.turso_auth_token:
        print("Falta TURSO_AUTH_TOKEN en el entorno o .env")
        sys.exit(1)

    print("Probando Turso:", settings.turso_url)
    db.setup()
    with db.connect() as conn:
        conn.execute("SELECT COUNT(*) AS n FROM jugadores")
        print("Jugadores:", conn.fetchone()["n"])
        conn.execute("SELECT COUNT(*) AS n FROM guild_config")
        print("Servidores configurados:", conn.fetchone()["n"])
    print("Turso OK")


if __name__ == "__main__":
    main()
