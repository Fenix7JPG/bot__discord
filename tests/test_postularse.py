"""Tests del cog /postularse-trabajo: postulaciones segun experiencia."""

import random as modulo_random
from unittest.mock import MagicMock

import pytest

from cogs.economia.postularse_trabajo import PostularseTrabajo
from database import jugadores_repo
from tests.fakes import FabricaInteraccion

SLUG = "lavaplatos"  # requiere 2 XP, sueldo 9


@pytest.fixture()
def cog(db_local):
    return PostularseTrabajo(MagicMock())


@pytest.fixture()
def jugador(db_local):
    jugadores_repo.crear_jugador(111)
    return 111


async def test_postularse_sin_perfil(cog):
    """Sin /jugar previo no se puede postular."""
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "postularse_trabajo", inter, trabajo=SLUG)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "/jugar" in enviado["content"]


async def test_postularse_trabajo_inexistente(cog, jugador):
    """Un slug desconocido devuelve efimero con ejemplos reales del catalogo."""
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "postularse_trabajo", inter, trabajo="trabajo-fantasma")

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "trabajo-fantasma" in enviado["content"]
    assert "recogedor-de-basura" in enviado["content"]  # ejemplo del catalogo real
    assert jugadores_repo.get_jugador(111)["trabajo"] is None


async def test_postularse_aceptado_con_experiencia_suficiente(cog, jugador):
    """Con XP >= requerida la aceptacion es segura y guarda el trabajo."""
    jugadores_repo.actualizar_campo(111, "experiencia", 10)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "postularse_trabajo", inter, trabajo=SLUG)

    contenido = inter.response.mensajes[0]["content"]
    assert "Felicidades" in contenido
    assert "<@111>" in contenido  # mencion al usuario
    assert "Lavaplatos" in contenido
    assert jugadores_repo.get_jugador(111)["trabajo"] == SLUG


async def test_postularse_rechazado_sin_experiencia(cog, jugador, monkeypatch):
    """Sin XP y con mala suerte el rechazo deja el perfil sin trabajo."""
    monkeypatch.setattr(modulo_random, "random", lambda: 0.99)  # > 0.3
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "postularse_trabajo", inter, trabajo=SLUG)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "No te aceptaron" in enviado["content"]
    assert "2 XP" in enviado["content"]  # requerida del lavaplatos
    assert jugadores_repo.get_jugador(111)["trabajo"] is None


async def test_postularse_suerte_sin_experiencia(cog, jugador, monkeypatch):
    """Sin XP pero con suerte entra igual (30% de probabilidad)."""
    monkeypatch.setattr(modulo_random, "random", lambda: 0.1)  # < 0.3
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "postularse_trabajo", inter, trabajo=SLUG)

    contenido = inter.response.mensajes[0]["content"]
    assert "Felicidades" in contenido
    assert "suerte" in contenido.lower()
    assert jugadores_repo.get_jugador(111)["trabajo"] == SLUG


async def test_postularse_mismo_trabajo_actual(cog, jugador):
    """Postularse al trabajo que ya se tiene avisa sin repetir registro."""
    jugadores_repo.actualizar_campo(111, "trabajo", SLUG)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "postularse_trabajo", inter, trabajo=SLUG)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "Ya trabajas como" in enviado["content"]


async def test_postularse_busca_por_nombre_completo(cog, jugador):
    """La busqueda tambien funciona con el nombre visible del trabajo."""
    jugadores_repo.actualizar_campo(111, "experiencia", 99)

    await FabricaInteraccion.invocar(
        cog, "postularse_trabajo", FabricaInteraccion.interaccion(user_id=111), trabajo="Lavaplatos"
    )

    assert jugadores_repo.get_jugador(111)["trabajo"] == SLUG
