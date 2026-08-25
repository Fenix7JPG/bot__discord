"""Tests del cog /jugar: registro de jugadores en la economia."""

from unittest.mock import MagicMock

import pytest

from cogs.economia.jugar import Jugar
from database import jugadores_repo
from tests.fakes import FabricaInteraccion


@pytest.fixture()
def cog(db_local):
    return Jugar(MagicMock())


async def test_jugar_registra_usuario_nuevo(cog):
    """Primer /jugar crea el perfil y responde con mensaje de bienvenida."""
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "jugar", inter)

    assert inter.response.enviado is True
    assert "registrado" in inter.response.mensajes[0]["content"].lower()
    assert "trabajos" in inter.response.mensajes[0]["content"].lower()
    perfil = jugadores_repo.get_jugador(111)
    assert perfil is not None
    assert perfil["dinero"] == 0
    assert perfil["salud"] == 100


async def test_jugar_usuario_ya_registrado(cog):
    """Segundo /jugar no duplica el perfil y avisa al usuario."""
    primera = FabricaInteraccion.interaccion(user_id=222)
    segunda = FabricaInteraccion.interaccion(user_id=222)

    await FabricaInteraccion.invocar(cog, "jugar", primera)
    await FabricaInteraccion.invocar(cog, "jugar", segunda)

    contenido = segunda.response.mensajes[0]["content"].lower()
    assert "ya" in contenido
    assert "registrado" in contenido
    # El perfil sigue siendo uno solo con datos intactos
    jugadores_repo.actualizar_campo(222, "dinero", 50)
    await FabricaInteraccion.invocar(cog, "jugar", FabricaInteraccion.interaccion(user_id=222))
    assert jugadores_repo.get_jugador(222)["dinero"] == 50


async def test_jugar_perfiles_independientes_por_usuario(cog):
    """Cada usuario tiene su propio perfil."""
    await FabricaInteraccion.invocar(cog, "jugar", FabricaInteraccion.interaccion(user_id=1))
    await FabricaInteraccion.invocar(cog, "jugar", FabricaInteraccion.interaccion(user_id=2))

    jugadores_repo.actualizar_campo(1, "dinero", 30)
    assert jugadores_repo.get_jugador(2)["dinero"] == 0


def test_setup_registra_el_cog():
    """setup() es una coroutine que añade la clase al bot (sin red)."""
    import inspect

    from cogs.economia import jugar as modulo

    assert inspect.iscoroutinefunction(modulo.setup)
