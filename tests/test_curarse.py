"""Tests del cog /curarse: curar salud pagando con costo cuadratico."""

from unittest.mock import MagicMock

import pytest

from cogs.economia.curarse import Curarse
from database import jugadores_repo
from tests.fakes import FabricaInteraccion


@pytest.fixture()
def cog(db_local):
    return Curarse(MagicMock())


def _jugador_herido(user_id, salud=50, dinero=1000, enfermedad=None):
    jugadores_repo.crear_jugador(user_id)
    jugadores_repo.actualizar_campos(
        user_id,
        {"salud": salud, "dinero": dinero, "enfermedad": enfermedad,
         "fecha_enfermedad": "2026-08-20T00:00:00+00:00" if enfermedad else None},
    )
    return user_id


async def test_curarse_sin_perfil(cog):
    """Sin /jugar previo no se puede curar."""
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "curarse", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "/jugar" in enviado["content"]


async def test_curarse_con_salud_completa_no_cobra(cog):
    """Con 100 de salud avisa que no hace falta curarse."""
    _jugador_herido(111, salud=100)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "curarse", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "salud completa" in enviado["content"].lower()
    assert jugadores_repo.get_jugador(111)["dinero"] == 1000


async def test_curarse_por_defecto_cura_todo_el_faltante(cog):
    """Sin cantidad cura hasta 100: 50 vida cuestan 5x50 + 0.2x2500 = 750."""
    _jugador_herido(111, salud=50, dinero=1000)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "curarse", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "<@111>" in contenido
    assert "$750" in contenido
    assert "50 -> 100" in contenido
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["salud"] == 100
    assert perfil["dinero"] == 250


async def test_curarse_cantidad_parcial(cog):
    """Pedir 10 de vida cuesta 10x5 + 0.2x100 = 70."""
    _jugador_herido(222, salud=50, dinero=500)
    inter = FabricaInteraccion.interaccion(user_id=222)

    await FabricaInteraccion.invocar(cog, "curarse", inter, cantidad=10)

    assert "50 -> 60" in inter.response.mensajes[0]["content"]
    perfil = jugadores_repo.get_jugador(222)
    assert perfil["salud"] == 60
    assert perfil["dinero"] == 430


async def test_curarse_cantidad_mayor_al_faltante_se_recorta(cog):
    """Pedir mas de lo que falta solo cura el faltante."""
    _jugador_herido(333, salud=90, dinero=1000)
    inter = FabricaInteraccion.interaccion(user_id=333)

    await FabricaInteraccion.invocar(cog, "curarse", inter, cantidad=9999)

    # faltante 10: costo 10x5 + 0.2x100 = 70
    assert "90 -> 100" in inter.response.mensajes[0]["content"]
    assert jugadores_repo.get_jugador(333)["dinero"] == 930


async def test_curarse_sin_dinero_suficiente_rechaza(cog):
    """Si el costo supera el dinero no cambia nada del perfil."""
    _jugador_herido(444, salud=10, dinero=10)  # faltante 90: costo 450+1620
    inter = FabricaInteraccion.interaccion(user_id=444)

    await FabricaInteraccion.invocar(cog, "curarse", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "No tienes suficiente dinero" in enviado["content"]
    assert "2070" in enviado["content"]
    perfil = jugadores_repo.get_jugador(444)
    assert perfil["salud"] == 10
    assert perfil["dinero"] == 10


async def test_curarse_cantidad_negativa_cura_todo(cog):
    """Una cantidad <= 0 se interpreta como curar todo el faltante."""
    _jugador_herido(555, salud=80, dinero=300)
    inter = FabricaInteraccion.interaccion(user_id=555)

    await FabricaInteraccion.invocar(cog, "curarse", inter, cantidad=-5)

    # faltante 20: costo 20x5 + 0.2x400 = 180
    assert "80 -> 100" in inter.response.mensajes[0]["content"]
    assert jugadores_repo.get_jugador(555)["dinero"] == 120


async def test_curarse_a_100_o_mas_limpia_la_enfermedad(cog):
    """Llegar a >= 80 de salud da por superada la enfermedad."""
    _jugador_herido(666, salud=70, dinero=1000, enfermedad="Gripe")
    inter = FabricaInteraccion.interaccion(user_id=666)

    await FabricaInteraccion.invocar(cog, "curarse", inter)

    perfil = jugadores_repo.get_jugador(666)
    assert perfil["salud"] == 100
    assert perfil["enfermedad"] is None
    assert perfil["fecha_enfermedad"] is None


async def test_curarse_por_debajo_de_80_mantiene_la_enfermedad(cog):
    """Si la curacion no alcanza 80 la enfermedad sigue ahi."""
    _jugador_herido(777, salud=50, dinero=1000, enfermedad="Gripe")
    inter = FabricaInteraccion.interaccion(user_id=777)

    await FabricaInteraccion.invocar(cog, "curarse", inter, cantidad=20)

    perfil = jugadores_repo.get_jugador(777)
    assert perfil["salud"] == 70
    assert perfil["enfermedad"] == "Gripe"
