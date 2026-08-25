"""Configura pytest para los tests del bot.

Fijtures clave:
    - event_loop global: un solo loop asyncio para toda la sesión (discord.py
      y pytest-asyncio conviven mejor así).
    - db_local: fuerza la capa de datos a SQLite en archivo temporal.
    - fabrica_interaccion: crea Interactions falsas sin conectar a Discord.
"""

import asyncio
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Raíz del proyecto en sys.path para importar bot/, cogs/, database/...
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def db_local(tmp_path, monkeypatch):
    """Base SQLite temporal; cada test arranca con tablas limpias."""
    from config import settings

    monkeypatch.setattr(settings, "db_mode", "local")
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    from database.database import db

    db.mode = "local"
    db.setup()
    return db


@pytest_asyncio.fixture
async def fabrica_interaccion():
    """Devuelve una función que crea interacciones falsas de Discord.

    La fake captura todo lo que el comando envía (mensajes, embeds, vistas)
    para que los tests puedan afirmar sobre ellos sin red ni Discord real.
    """
    from tests.fakes import FabricaInteraccion

    return FabricaInteraccion()


def pytest_collection_modifyitems(items):
    # Todos los tests async corren con el fixture de pytest-asyncio por defecto
    import inspect

    for item in items:
        if inspect.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
