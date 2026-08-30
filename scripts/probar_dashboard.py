"""Levanta el dashboard (/panel) en local para probarlo a mano.

Uso: python scripts/probar_dashboard.py
Requiere en .env: DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET y
DASHBOARD_PUBLIC_URL (por ejemplo http://localhost:5000).
En el portal de Discord, la redirect URI debe ser
DASHBOARD_PUBLIC_URL + /panel/callback
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)


def main():
    from config import settings
    from database.database import db

    if not settings.discord_client_id or not settings.discord_client_secret:
        print("Faltan DISCORD_CLIENT_ID o DISCORD_CLIENT_SECRET en el .env.")
        print("El panel abrira, pero el login con Discord fallara.")

    db.setup()
    print("Modo de BD:", db.mode)

    from services.dashboard import crear_app

    app = crear_app()
    puerto = int(os.getenv("PORT", "5000"))
    print("Panel disponible en: http://localhost:" + str(puerto) + "/panel")
    print("Ctrl+C para salir.")
    app.run(host="127.0.0.1", port=puerto)


if __name__ == "__main__":
    main()
