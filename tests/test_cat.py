"""Tests del cog /cat: seleccion de fuente y manejo de fallos (sin red).

La sesion HTTP se simula para controlar que responde cada API.
"""

from unittest.mock import MagicMock

import pytest

from cogs.diversion.cat import Cat
from tests.fakes import FabricaInteraccion


@pytest.fixture()
def cog(db_local):
    return Cat(MagicMock())


def _sesion_falsa(monkeypatch, cog, respuestas):
    """Reemplaza la session del cog por un objeto controlable.

    respuestas es una lista: cada posicion es la respuesta de una fuente,
    consumida en orden. Puede ser {"status": 200, "json": ...} o None/500
    para simular error.
    """
    cola = iter(list(respuestas) + [None] * 10)

    class RespuestaFalsa:
        def __init__(self, spec):
            self.status = spec["status"] if spec else 500
            self._json = spec.get("json") if spec else None

        async def json(self):
            return self._json

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class SesionFalsa:
        def get(self, url_api, timeout=None):
            return RespuestaFalsa(next(cola))

    cog.session = SesionFalsa()


async def test_cat_envia_embed_con_imagen(cog, monkeypatch):
    """Caso feliz: la primera API responde y el embed lleva la imagen."""
    _sesion_falsa(monkeypatch, cog, [{"status": 200, "json": [{"url": "https://gato.com/foto.jpg"}]}])
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "cat", inter)

    enviado = inter.followup.mensajes[0]
    assert enviado["embed"] is not None
    assert enviado["embed"].image.url == "https://gato.com/foto.jpg"


async def test_cat_prueba_la_siguiente_fuente_si_una_falla(cog, monkeypatch):
    """Si la primera API falla usa la segunda (random.cat devuelve 'file')."""
    _sesion_falsa(
        monkeypatch,
        cog,
        [
            {"status": 500},
            {"status": 200, "json": {"file": "https://random.cat/gato.png"}},
        ],
    )
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "cat", inter)

    embed = inter.followup.mensajes[0]["embed"]
    assert embed.image.url == "https://random.cat/gato.png"


async def test_cat_sin_ninguna_fuente_disponible_avisa(cog):
    """Con todas las APIs caidas avisa amablemente."""
    cog.session = None
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "cat", inter)

    contenido = inter.followup.mensajes[0]["content"]
    assert "gatito" in contenido.lower() or "no pude" in contenido.lower()
