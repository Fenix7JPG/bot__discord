"""Tests de los dados /d6, /d10 y /d20."""

import random as modulo_random
from unittest.mock import MagicMock

import pytest

from cogs.diversion.dados import Dados
from tests.fakes import FabricaInteraccion


@pytest.fixture()
def cog():
    return Dados(MagicMock())


def _fijar_tirada(monkeypatch, valor):
    llamadas = []

    def randint_falso(a, b):
        llamadas.append((a, b))
        return valor if valor <= b else b

    monkeypatch.setattr(modulo_random, "randint", randint_falso)
    return llamadas


async def test_d6_devuelve_el_valor_tirado(cog, monkeypatch):
    """El d6 anuncia el numero y usa el rango 1..6."""
    llamadas = _fijar_tirada(monkeypatch, 4)
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "d6", inter)

    assert "**4**" in inter.response.mensajes[0]["content"]
    assert "d6" in inter.response.mensajes[0]["content"]
    assert llamadas[-1] == (1, 6)


async def test_d10_respeta_su_rango(cog, monkeypatch):
    """El d10 tira entre 1 y 10."""
    llamadas = _fijar_tirada(monkeypatch, 10)
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "d10", inter)

    assert "**10**" in inter.response.mensajes[0]["content"]
    assert llamadas[-1] == (1, 10)


async def test_d20_respeta_su_rango(cog, monkeypatch):
    """El d20 tira entre 1 y 20."""
    llamadas = _fijar_tirada(monkeypatch, 20)
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "d20", inter)

    assert "**20**" in inter.response.mensajes[0]["content"]
    assert llamadas[-1] == (1, 20)


async def test_dados_sin_random_mockeado_siguen_en_rango(cog):
    """Con aleatoriedad real los resultados siguen dentro del rango."""
    for nombre, maximo in (("d6", 6), ("d10", 10), ("d20", 20)):
        inter = FabricaInteraccion.interaccion(user_id=1)
        await FabricaInteraccion.invocar(cog, nombre, inter)
        contenido = inter.response.mensajes[0]["content"]
        numero = int(contenido.split("**")[-2])
        assert 1 <= numero <= maximo
