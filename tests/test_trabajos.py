"""Tests del cog /trabajos: lista paginada con botones."""

from unittest.mock import MagicMock

import pytest

from cogs.economia.trabajos import TRABAJOS_POR_PAGINA, Trabajos, VistaTrabajos
from tests.fakes import FabricaInteraccion
from utils import datos


@pytest.fixture()
def cog(db_local):
    return Trabajos(MagicMock())


@pytest.fixture()
def trabajos_reales():
    return datos.obtener_trabajos()


async def test_trabajos_envia_lista_paginada(cog):
    """Con trabajos en el JSON envia embed paginado via followup."""
    inter = FabricaInteraccion.interaccion(user_id=7)

    await FabricaInteraccion.invocar(cog, "trabajos", inter)

    assert inter.response.enviado is True  # hizo defer
    assert len(inter.followup.mensajes) == 1
    enviado = inter.followup.mensajes[0]
    assert enviado["embed"] is not None
    assert "Trabajos" in enviado["embed"].title
    assert enviado["view"] is not None
    # Primera pagina llena
    assert len(enviado["embed"].fields) == TRABAJOS_POR_PAGINA


async def test_trabajos_sin_catalogo_responde_efimero(cog, monkeypatch):
    """Sin trabajos disponibles avisa con mensaje efimero y no manda vista."""
    monkeypatch.setattr(datos, "obtener_trabajos", lambda: [])
    inter = FabricaInteraccion.interaccion(user_id=7)

    await FabricaInteraccion.invocar(cog, "trabajos", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "No hay trabajos" in contenido
    assert inter.response.mensajes[0]["ephemeral"] is True


def test_vista_primera_pagina_y_descripcion(vista_factory):
    """La vista arranca en pagina 1 con el total en la descripcion."""
    vista, trabajos = vista_factory()

    embed = vista.construir_embed()

    assert vista.pagina == 0
    assert "Pagina 1/" in embed.description
    assert str(len(trabajos)) + " trabajos" in embed.description
    assert len(embed.fields) == TRABAJOS_POR_PAGINA
    assert vista.boton_anterior.disabled is True
    assert vista.boton_siguiente.disabled is False


def test_vista_ultima_pagina_calculada(vista_factory):
    """La ultima pagina depende del tamaño del catalogo."""
    vista, _ = vista_factory()

    esperada = (len(vista.trabajos) - 1) // TRABAJOS_POR_PAGINA
    assert vista.ultima_pagina == esperada


async def test_boton_siguiente_avanza_pagina(vista_factory):
    """El boton ➡️ pasa a la pagina 2 y edita el mensaje."""
    vista, _ = vista_factory()
    inter = FabricaInteraccion.interaccion(user_id=1)

    await vista.boton_siguiente.callback(inter)

    assert vista.pagina == 1
    assert len(inter.response.ediciones) == 1
    nuevo_embed = inter.response.ediciones[0]["embed"]
    assert "Pagina 2/" in nuevo_embed.description


async def test_boton_anterior_no_baja_de_cero(vista_factory):
    """El boton ⬅️ en pagina 1 se queda en pagina 1 pero edita igual."""
    vista, _ = vista_factory()
    inter = FabricaInteraccion.interaccion(user_id=1)

    await vista.boton_anterior.callback(inter)

    assert vista.pagina == 0
    assert len(inter.response.ediciones) == 1


async def test_boton_cerrar_deshabilita_todo(vista_factory):
    """El boton ⏹️ cierra la lista: todos los botones quedan apagados."""
    vista, _ = vista_factory()
    inter = FabricaInteraccion.interaccion(user_id=1)

    await vista.boton_cerrar.callback(inter)

    assert all(child.disabled for child in vista.children)
    edicion = inter.response.ediciones[0]
    assert edicion["content"] == "Lista cerrada."
    assert edicion["embed"] is None


async def test_interaction_check_bloquea_a_otro_usuario(vista_factory):
    """Solo quien abrio la lista puede pulsar los botones."""
    vista, _ = vista_factory()

    ajena = FabricaInteraccion.interaccion(user_id=999)
    propia = FabricaInteraccion.interaccion(user_id=vista.autor_id)

    assert await vista.interaction_check(ajena) is False
    assert ajena.response.mensajes[0]["ephemeral"] is True
    assert await vista.interaction_check(propia) is True


@pytest.fixture()
def vista_factory(trabajos_reales):
    def crear(cantidad=None, autor_id=1):
        lista = trabajos_reales if cantidad is None else trabajos_reales[:cantidad]
        return VistaTrabajos(lista, autor_id), lista

    return crear
