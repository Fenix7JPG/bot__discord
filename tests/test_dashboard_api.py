"""Tests de las rutas del dashboard con test_client de Flask (feature 001).

Sin red ni Discord: el flujo OAuth se simula (HTTP falso en el callback) y
la sesion web se prepara con session_transaction.
"""

import json
import time
from unittest.mock import MagicMock

import pytest

from database import servidor_repo


GUILD_ADMIN = 100
GUILD_OTRO = 300


class _RespuestaFalsa:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


@pytest.fixture()
def app(db_local):
    """App Flask del panel con un bot falso presente en 2 servidores."""
    from services.dashboard import crear_app, registrar_bot

    bot = MagicMock()
    guilds = []
    for guild_id in (GUILD_ADMIN, 200):
        guild = MagicMock()
        guild.id = guild_id
        guilds.append(guild)
    bot.guilds = guilds
    registrar_bot(bot)
    return crear_app()


@pytest.fixture()
def cliente(app):
    return app.test_client()


def _con_sesion(cliente, admin_guilds=(GUILD_ADMIN,)):
    """Prepara la cookie de sesion como lo haria el callback."""
    with cliente.session_transaction() as ses:
        ses["discord_id"] = 123
        ses["username"] = "admin_test"
        ses["admin_guilds"] = list(admin_guilds)
        ses["creada"] = time.time()


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------


def test_panel_sin_sesion_muestra_login(cliente):
    respuesta = cliente.get("/panel")
    assert respuesta.status_code == 200
    cuerpo = respuesta.data.decode("utf-8")
    assert "Discord" in cuerpo
    assert "/panel/login" in cuerpo


def test_panel_con_sesion_lista_solo_admin_y_presentes(cliente):
    _con_sesion(cliente, admin_guilds=(GUILD_ADMIN, GUILD_OTRO))
    respuesta = cliente.get("/panel")
    cuerpo = respuesta.data.decode("utf-8")
    # 100 es admin Y el bot esta; 300 es admin pero el bot NO esta; 200 bot sin admin
    assert "/panel/servidor/100" in cuerpo
    assert "/panel/servidor/300" not in cuerpo
    assert "/panel/servidor/200" not in cuerpo


def test_pagina_servidor_admin_200(cliente):
    _con_sesion(cliente)
    respuesta = cliente.get("/panel/servidor/100")
    assert respuesta.status_code == 200
    cuerpo = respuesta.data.decode("utf-8")
    assert "work_mode" in cuerpo
    assert "turns_per_session" in cuerpo
    assert "welcome_channel_id" in cuerpo
    assert "auditoria" in cuerpo.lower()


def test_pagina_servidor_sin_sesion_401(cliente):
    respuesta = cliente.get("/panel/servidor/100")
    assert respuesta.status_code == 401


def test_pagina_servidor_no_admin_403(cliente):
    _con_sesion(cliente, admin_guilds=(GUILD_OTRO,))
    respuesta = cliente.get("/panel/servidor/100")
    assert respuesta.status_code == 403
    assert "acceso" in respuesta.data.decode("utf-8").lower()


def test_estaticos_servidos(cliente):
    css = cliente.get("/panel/panel.css")
    js = cliente.get("/panel/panel.js")
    assert css.status_code == 200
    assert "text/css" in css.headers["Content-Type"]
    assert js.status_code == 200
    assert "javascript" in js.headers["Content-Type"]


# ---------------------------------------------------------------------------
# Callback OAuth (con HTTP falso)
# ---------------------------------------------------------------------------


def _instalar_http_falso(monkeypatch, respuestas):
    from services.dashboard import auth

    def urlopen_falso(req, timeout=None):
        respuesta = respuestas.pop(0)
        return _RespuestaFalsa(json.dumps(respuesta).encode("utf-8"))

    monkeypatch.setattr(auth.urllib.request, "urlopen", urlopen_falso)


def test_callback_state_invalido_rechaza(cliente):
    respuesta = cliente.get("/panel/callback?code=codigo&state=invalido")
    assert respuesta.status_code == 400
    with cliente.session_transaction() as ses:
        assert "discord_id" not in ses, "no debe crear sesion"


def test_callback_valido_crea_sesion(cliente, monkeypatch):
    _instalar_http_falso(
        monkeypatch,
        [
            {"access_token": "tok", "token_type": "Bearer"},
            {"id": "123", "username": "admin_test"},
            [
                {"id": str(GUILD_ADMIN), "name": "Mi Server", "permissions": "8"},
                {"id": "999", "name": "No admin", "permissions": "0"},
            ],
        ],
    )
    with cliente.session_transaction() as ses:
        ses["oauth_state"] = "estado-ok"

    respuesta = cliente.get("/panel/callback?code=codigo&state=estado-ok")

    assert respuesta.status_code == 302
    with cliente.session_transaction() as ses:
        assert ses["discord_id"] == 123
        assert GUILD_ADMIN in ses["admin_guilds"]
        assert 999 not in ses["admin_guilds"]


def test_logout_limpia_sesion(cliente):
    _con_sesion(cliente)
    respuesta = cliente.get("/panel/logout")
    assert respuesta.status_code == 302
    with cliente.session_transaction() as ses:
        assert "discord_id" not in ses


# ---------------------------------------------------------------------------
# API de configuracion
# ---------------------------------------------------------------------------


def test_api_guardar_config_valida(cliente):
    _con_sesion(cliente)
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"turns_per_session": 5}),
        content_type="application/json",
    )
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["ok"] is True
    assert datos["cambios"][0]["campo"] == "turns_per_session"
    assert datos["cambios"][0]["nuevo"] == 5
    config = servidor_repo.get_economia(100)
    assert config["turns_per_session"] == 5


def test_api_guardar_config_invalida_rechaza_completo(cliente):
    _con_sesion(cliente)
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"turns_per_session": 3, "sessions_per_day": 99}),
        content_type="application/json",
    )
    assert respuesta.status_code == 400
    datos = respuesta.get_json()
    assert datos["ok"] is False
    config = servidor_repo.get_economia(100)
    assert config["turns_per_session"] == 3, "no debe tocar nada si hay un campo invalido"


def test_api_guardar_config_general_ids(cliente, db_local):
    _con_sesion(cliente)
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"welcome_channel_id": "555", "hunter_role_id": ""}),
        content_type="application/json",
    )
    assert respuesta.status_code == 200
    assert servidor_repo.get_config(100, "welcome_channel_id") == 555


def test_api_guardar_config_general_invalido_400(cliente):
    _con_sesion(cliente)
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"welcome_channel_id": "no-es-numero"}),
        content_type="application/json",
    )
    assert respuesta.status_code == 400


def test_api_sin_sesion_401(cliente):
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"turns_per_session": 4}),
        content_type="application/json",
    )
    assert respuesta.status_code == 401


def test_api_no_admin_403(cliente):
    _con_sesion(cliente, admin_guilds=(GUILD_OTRO,))
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"turns_per_session": 4}),
        content_type="application/json",
    )
    assert respuesta.status_code == 403


def test_api_sin_json_415(cliente):
    _con_sesion(cliente)
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data="turns_per_session=4",
        content_type="text/plain",
    )
    assert respuesta.status_code == 415


def test_api_origin_incoherente_rechazado(cliente):
    _con_sesion(cliente)
    respuesta = cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"turns_per_session": 4}),
        content_type="application/json",
        headers={"Origin": "https://sitio-malicioso.example"},
    )
    assert respuesta.status_code == 403
    config = servidor_repo.get_economia(100)
    assert config["turns_per_session"] == 3, "el cambio no debe aplicarse"


def test_api_auditoria_endpoint(cliente):
    _con_sesion(cliente)
    cliente.post(
        "/panel/api/servidor/100/config",
        data=json.dumps({"minigame": "memoria"}),
        content_type="application/json",
    )
    respuesta = cliente.get("/panel/api/servidor/100/auditoria")
    assert respuesta.status_code == 200
    registros = respuesta.get_json()
    assert any(r["campo"] == "minigame" for r in registros)
