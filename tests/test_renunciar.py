"""Tests del cog /renunciar-trabajo (feature 001)."""

from unittest.mock import MagicMock

import pytest

from cogs.economia.renunciar_trabajo import RenunciarTrabajo
from database import jugadores_repo
from tests.fakes import FabricaInteraccion


@pytest.fixture()
def cog(db_local):
    return RenunciarTrabajo(MagicMock())


@pytest.fixture()
def jugador_con_trabajo(db_local):
    jugadores_repo.crear_jugador(111)
    jugadores_repo.actualizar_campo(111, "trabajo", "lavaplatos")
    return 111


async def test_renunciar_sin_profesion_avisa(cog, db_local):
    """Sin profesion no hay nada que renunciar."""
    jugadores_repo.crear_jugador(222)
    inter = FabricaInteraccion.interaccion(user_id=222)

    await FabricaInteraccion.invocar(cog, "renunciar_trabajo", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "No tienes" in enviado["content"] or "no tienes" in enviado["content"].lower()


async def test_renunciar_con_profesion_pide_confirmacion(cog, jugador_con_trabajo):
    """Con profesion envia la vista de Confirmar/Cancelar."""
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "renunciar_trabajo", inter)

    mensaje = inter.response.mensajes[0]
    assert mensaje["view"] is not None
    assert "Lavaplatos" in mensaje["content"]
    etiquetas = [child.label for child in mensaje["view"].children]
    assert "Confirmar" in etiquetas
    assert "Cancelar" in etiquetas


async def test_confirmar_deja_sin_profesion(cog, jugador_con_trabajo):
    """Confirmar borra el trabajo y lo informa."""
    inter = FabricaInteraccion.interaccion(user_id=111)
    await FabricaInteraccion.invocar(cog, "renunciar_trabajo", inter)
    vista = inter.response.mensajes[0]["view"]

    presion = FabricaInteraccion.interaccion(user_id=111)
    await vista.manejar_respuesta(presion, True)

    assert jugadores_repo.get_jugador(111)["trabajo"] is None
    contenido = presion.response.ediciones[0]["content"]
    assert "renunciaste" in contenido.lower()


async def test_cancelar_no_cambia_nada(cog, jugador_con_trabajo):
    """Cancelar conserva el trabajo actual."""
    inter = FabricaInteraccion.interaccion(user_id=111)
    await FabricaInteraccion.invocar(cog, "renunciar_trabajo", inter)
    vista = inter.response.mensajes[0]["view"]

    presion = FabricaInteraccion.interaccion(user_id=111)
    await vista.manejar_respuesta(presion, False)

    assert jugadores_repo.get_jugador(111)["trabajo"] == "lavaplatos"
    contenido = presion.response.ediciones[0]["content"]
    assert "seguis" in contenido.lower() or "mantienes" in contenido.lower()


async def test_tercero_no_puede_confirmar(cog, jugador_con_trabajo):
    """Un usuario distinto al que renuncia recibe aviso efimero."""
    inter = FabricaInteraccion.interaccion(user_id=111)
    await FabricaInteraccion.invocar(cog, "renunciar_trabajo", inter)
    vista = inter.response.mensajes[0]["view"]

    ajeno = FabricaInteraccion.interaccion(user_id=999)
    await vista.manejar_respuesta(ajeno, True)

    assert ajeno.response.mensajes[0]["ephemeral"] is True
    assert jugadores_repo.get_jugador(111)["trabajo"] == "lavaplatos"
