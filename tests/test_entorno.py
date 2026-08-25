"""Prueba el entorno de tests: fakes y base de datos temporal."""

import pytest


def test_imports_proyecto():
    import config  # noqa: F401
    import database.database  # noqa: F401
    from utils import datos as utiles  # noqa: F401


@pytest.mark.asyncio
async def test_interaccion_falsa_responde(db_local, fabrica_interaccion):
    from commands_dummy import comando_de_prueba

    inter = fabrica_interaccion.interaccion(user_id=7)
    await comando_de_prueba(inter)
    assert inter.response.enviado
    assert "pong" in inter.response.mensajes[0]["content"]
