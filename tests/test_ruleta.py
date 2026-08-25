"""Tests del cog /ruleta: colores, cero y liquidacion de apuestas."""

import random as modulo_random
from unittest.mock import MagicMock

import pytest

from cogs.diversion.ruleta import NUMEROS_ROJOS, Ruleta
from database import jugadores_repo
from tests.fakes import FabricaInteraccion


@pytest.fixture()
def cog(db_local):
    return Ruleta(MagicMock())


@pytest.fixture()
def jugador(db_local):
    jugadores_repo.crear_jugador(111)
    jugadores_repo.actualizar_campo(111, "dinero", 100)
    return 111


def _fijar_numero(monkeypatch, numero):
    monkeypatch.setattr(modulo_random, "randint", lambda a, b: numero)


def _campo(embed, nombre):
    return next(f for f in embed.fields if f.name == nombre).value


async def test_ruleta_opcion_invalida(cog):
    """Solo se acepta rojo, negro o cero."""
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="verde", apuesta=10)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "Opción inválida" in enviado["content"]


async def test_ruleta_apuesta_no_positiva(cog, jugador):
    """La apuesta debe ser mayor que 0."""
    for mala in (0, -3):
        inter = FabricaInteraccion.interaccion(user_id=111)
        await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="rojo", apuesta=mala)
        assert "mayor que 0" in inter.response.mensajes[0]["content"]


async def test_ruleta_sin_perfil(cog):
    """Sin /jugar previo avisa efimero."""
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="rojo", apuesta=10)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "/jugar" in enviado["content"]


async def test_ruleta_dinero_insuficiente(cog, jugador):
    """No se puede apostar mas que el saldo disponible."""
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="rojo", apuesta=999)

    contenido = inter.response.mensajes[0]["content"]
    assert "suficiente dinero" in contenido
    assert "$100" in contenido


async def test_ruleta_gana_al_rojo(cog, jugador, monkeypatch):
    """Numero rojo apostando a rojo paga 1:1."""
    _fijar_numero(monkeypatch, 5)  # 5 es rojo
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="rojo", apuesta=10)

    embed = inter.response.mensajes[0]["embed"]
    assert "🔴" in _campo(embed, "Resultado")
    assert "Ganaste" in _campo(embed, "Nota")
    assert "$10" in _campo(embed, "Nota")  # beneficio neto
    assert jugadores_repo.get_jugador(111)["dinero"] == 110  # 100 - 10 + 20


async def test_ruleta_pierde_contra_color_contrario(cog, jugador, monkeypatch):
    """Numero rojo apostando a negro pierde la apuesta."""
    _fijar_numero(monkeypatch, 5)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="negro", apuesta=10)

    embed = inter.response.mensajes[0]["embed"]
    assert "Perdiste" in _campo(embed, "Nota")
    assert jugadores_repo.get_jugador(111)["dinero"] == 90


async def test_ruleta_cero_paga_35_a_1(cog, jugador, monkeypatch):
    """Apostar al cero y salir el cero paga 35:1."""
    _fijar_numero(monkeypatch, 0)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="0", apuesta=10)

    embed = inter.response.mensajes[0]["embed"]
    assert "🟢" in _campo(embed, "Resultado")
    assert "35:1" in _campo(embed, "Nota")
    assert jugadores_repo.get_jugador(111)["dinero"] == 450  # 100 - 10 + 360


async def test_ruleta_cero_no_es_ni_rojo_ni_negro(cog, jugador, monkeypatch):
    """El cero hace perder a quien apostó a un color."""
    _fijar_numero(monkeypatch, 0)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="rojo", apuesta=10)

    assert "Perdiste" in _campo(inter.response.mensajes[0]["embed"], "Nota")
    assert jugadores_repo.get_jugador(111)["dinero"] == 90


async def test_ruleta_acepta_alias(cog, jugador, monkeypatch):
    """Los alias r/n/RED y cero funcionan igual."""
    _fijar_numero(monkeypatch, 3)  # rojo

    for alias in ("r", "RED"):
        inter = FabricaInteraccion.interaccion(user_id=111)
        await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion=alias, apuesta=2)
        assert "Ganaste" in _campo(inter.response.mensajes[0]["embed"], "Nota")

    _fijar_numero(monkeypatch, 8)  # negro
    inter = FabricaInteraccion.interaccion(user_id=111)
    await FabricaInteraccion.invocar(cog, "ruleta", inter, opcion="n", apuesta=2)
    assert "Ganaste" in _campo(inter.response.mensajes[0]["embed"], "Nota")


def test_numeros_rojos_son_18():
    """La ruleta europea tiene 18 numeros rojos mas el cero aparte."""
    assert len(NUMEROS_ROJOS) == 18
    assert 0 not in NUMEROS_ROJOS
