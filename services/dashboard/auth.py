"""Autenticacion OAuth2 de Discord para el dashboard.

Flujo Authorization Code con stdlib (urllib), sin dependencias nuevas:
login -> callback con code -> token -> /users/@me y /users/@me/guilds.
Las credenciales y la URL publica llegan por config.py (variables de entorno).
"""

import json
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from config import settings

URL_AUTORIZAR = "https://discord.com/oauth2/authorize"
URL_TOKEN = "https://discord.com/api/oauth2/token"
URL_YO = "https://discord.com/api/users/@me"
URL_MIS_GUILDS = "https://discord.com/api/users/@me/guilds"

PERMISO_ADMINISTRADOR = 0x8
PERMISO_MANEJAR_SERVIDOR = 0x20

_clave_aleatoria: str | None = None


def clave_firma() -> str:
    """Clave para firmar la cookie de sesion del panel.

    Orden: DASHBOARD_SECRET, LOG_PASSWORD, y como ultimo recurso una clave
    aleatoria por proceso (las sesiones previas dejan de valer al reiniciar).
    """
    global _clave_aleatoria
    if settings.dashboard_secret:
        return settings.dashboard_secret
    if settings.log_password:
        return settings.log_password
    if _clave_aleatoria is None:
        _clave_aleatoria = secrets.token_urlsafe(48)
    return _clave_aleatoria


def redirect_uri() -> str:
    """URL absoluta de callback registrada en el portal de Discord."""
    return settings.dashboard_public_url + "/panel/callback"


def construir_url_autorizacion(state: str) -> str:
    """URL de autorizacion de Discord con scope identify + guilds."""
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    }
    return URL_AUTORIZAR + "?" + urllib.parse.urlencode(params)


def _post_formulario(url: str, campos: dict) -> dict:
    datos = urllib.parse.urlencode(campos).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=datos,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, token: str) -> dict | list:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def intercambiar_codigo(code: str) -> dict:
    """Cambia el codigo de autorizacion por el token de acceso."""
    return _post_formulario(
        URL_TOKEN,
        {
            "client_id": settings.discord_client_id,
            "client_secret": settings.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri(),
        },
    )


def obtener_usuario_y_guilds(token_acceso: str) -> tuple[dict, list]:
    """Perfil del usuario y lista de servidores donde esta."""
    usuario = _get_json(URL_YO, token_acceso)
    guilds = _get_json(URL_MIS_GUILDS, token_acceso)
    return usuario, guilds


def extraer_admin_guilds(guilds: list) -> list[int]:
    """Ids de servidores donde el usuario es dueno, admin o maneja el servidor."""
    resultado: list[int] = []
    for guild in guilds:
        try:
            guild_id = int(guild.get("id"))
        except (TypeError, ValueError):
            continue
        if guild.get("owner"):
            resultado.append(guild_id)
            continue
        try:
            permisos = int(guild.get("permissions", "0") or 0)
        except (TypeError, ValueError):
            permisos = 0
        if permisos & (PERMISO_ADMINISTRADOR | PERMISO_MANEJAR_SERVIDOR):
            resultado.append(guild_id)
    return resultado


def guardar_cuenta(usuario: dict) -> None:
    """Guarda o actualiza la cuenta vinculada (dashboard_accounts)."""
    from database.database import db

    fecha = datetime.now(tz=timezone.utc).isoformat()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO dashboard_accounts (discord_id, username, ultimo_login)
            VALUES (?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                username = excluded.username,
                ultimo_login = excluded.ultimo_login
            """,
            (int(usuario["id"]), str(usuario.get("username", "")), fecha),
        )
