"""Configuración central del bot.

Lee variables de entorno (y un archivo .env si existe) y expone `settings`,
un objeto único para todo el proyecto.

Variables soportadas:
    DISCORD_TOKEN       token del bot de Discord
    COHERE_API_KEY      token para el servicio de IA (opcional)
    LOG_PASSWORD        contrasena del visor web /terminal (opcional)
    DB_MODE             "local" (sqlite) o "turso" (autodetecta si TURSO_URL existe)
    DB_PATH             ruta del archivo sqlite local
    TURSO_URL           URL libsql:// de la base en Turso
    TURSO_AUTH_TOKEN    token de autenticación de Turso
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv es opcional: sin él se usan solo las variables del entorno
    pass


class Settings:
    def __init__(self):
        self.discord_token = os.getenv("DISCORD_TOKEN", "")
        self.cohere_api_key = os.getenv("COHERE_API_KEY", "")
        self.log_password = os.getenv("LOG_PASSWORD", "")

        self.db_mode = os.getenv("DB_MODE", "")  # vacío = autodetectar
        self.db_path = os.getenv("DB_PATH", "datos/bot.db")

        self.turso_url = os.getenv(
            "TURSO_URL",
            "libsql://botdiscordzeku-fenix7jpg.aws-us-east-1.turso.io",
        )
        self.turso_auth_token = os.getenv("TURSO_AUTH_TOKEN", "")


settings = Settings()
