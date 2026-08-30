"""Tests del modulo de autenticacion OAuth2 del dashboard (feature 001).

Sin red real: urllib.request.urlopen se reemplaza por un doble que captura
las peticiones y devuelve respuestas JSON preparadas.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from services.dashboard import auth
from tests.fakes import FabricaInteraccion


class _RespuestaFalsa:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def _instalar_http_falso(monkeypatch, respuestas):
    """Reemplaza urlopen; devuelve la lista de peticiones recibidas."""
    peticiones = []

    def urlopen_falso(req, timeout=None):
        headers = getattr(req, "headers", {}) or {}
        peticiones.append({"url": req.full_url, "data": req.data, "headers": dict(headers)})
        respuesta = respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return _RespuestaFalsa(json.dumps(respuesta).encode("utf-8"))

    monkeypatch.setattr(auth.urllib.request, "urlopen", urlopen_falso)
    return peticiones


def test_construir_url_autorizacion():
    url = auth.construir_url_autorizacion("estado123")
    assert url.startswith("https://discord.com/oauth2/authorize")
    assert "client_id=" in url
    assert "redirect_uri=" in url
    assert "state=estado123" in url
    assert "response_type=code" in url
    assert "identify" in url and "guilds" in url


def test_intercambiar_codigo_envia_credenciales(monkeypatch):
    respuestas = [{"access_token": "tok", "token_type": "Bearer"}]
    peticiones = _instalar_http_falso(monkeypatch, respuestas)

    token = auth.intercambiar_codigo("codigo456")

    assert token["access_token"] == "tok"
    assert len(peticiones) == 1
    assert "/api/oauth2/token" in peticiones[0]["url"]
    cuerpo = peticiones[0]["data"].decode("utf-8")
    assert "codigo456" in cuerpo
    assert "authorization_code" in cuerpo


def test_intercambiar_codigo_error_propaga(monkeypatch):
    _instalar_http_falso(monkeypatch, [RuntimeError("400 Bad Request")])
    with pytest.raises(RuntimeError):
        auth.intercambiar_codigo("malo")


def test_obtener_usuario_y_guilds_usa_bearer(monkeypatch):
    respuestas = [
        {"id": "123", "username": "admin_test"},
        [{"id": "100", "name": "Guild", "permissions": "8"}],
    ]
    peticiones = _instalar_http_falso(monkeypatch, respuestas)

    usuario, guilds = auth.obtener_usuario_y_guilds("tok")

    assert usuario["username"] == "admin_test"
    assert guilds[0]["id"] == "100"
    assert len(peticiones) == 2
    assert "/users/@me/guilds" in peticiones[1]["url"]
    assert "Bearer tok" in peticiones[1]["headers"].get("Authorization", "")


def test_extraer_admin_guilds_filtra_por_permisos():
    guilds = [
        {"id": "100", "permissions": "8"},      # ADMINISTRADOR
        {"id": "200", "permissions": "0"},      # nada
        {"id": "300", "permissions": "32"},     # MANAGE_GUILD
        {"id": "400", "permissions": "2048"},   # otros permisos
        {"id": "500", "owner": True},           # dueno
    ]
    assert auth.extraer_admin_guilds(guilds) == [100, 300, 500]


def test_guardar_cuenta_persiste_iso_utc(db_local):
    auth.guardar_cuenta({"id": "123", "username": "admin_test"})

    from database.database import db

    with db.connect() as conn:
        conn.execute("SELECT * FROM dashboard_accounts WHERE discord_id = ?", (123,))
        fila = conn.fetchone()
    assert fila is not None
    assert fila["username"] == "admin_test"
    fecha = datetime.fromisoformat(fila["ultimo_login"])
    assert fecha.tzinfo is not None


def test_guardar_cuenta_actualiza_sin_duplicar(db_local):
    auth.guardar_cuenta({"id": "123", "username": "viejo"})
    auth.guardar_cuenta({"id": "123", "username": "nuevo"})

    from database.database import db

    with db.connect() as conn:
        conn.execute("SELECT COUNT(*) AS n FROM dashboard_accounts")
        n = conn.fetchone()["n"]
        conn.execute("SELECT username FROM dashboard_accounts WHERE discord_id = ?", (123,))
        fila = conn.fetchone()
    assert n == 1
    assert fila["username"] == "nuevo"


def test_clave_firma_con_dashboard_secret(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "dashboard_secret", "secreto-largo")
    assert auth.clave_firma() == "secreto-largo"


def test_clave_firma_cae_a_log_password(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "dashboard_secret", "")
    monkeypatch.setattr(settings, "log_password", "contrasena")
    assert auth.clave_firma() == "contrasena"


def test_clave_firma_aleatoria_si_no_hay_nada(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "dashboard_secret", "")
    monkeypatch.setattr(settings, "log_password", "")
    clave = auth.clave_firma()
    assert len(clave) >= 32, "la clave de respaldo debe ser aleatoria y larga"
