"""Tests del cog /stats: embed de estadisticas del jugador."""

from unittest.mock import MagicMock

import pytest

from cogs.economia.stats import Stats
from database import jugadores_repo
from tests.fakes import FabricaInteraccion


@pytest.fixture()
def cog(db_local):
    return Stats(MagicMock())


async def test_stats_sin_perfil(cog):
    """Sin /jugar previo avisa efimero en vez de romper."""
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "stats", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "/jugar" in enviado["content"]


async def test_stats_embed_completo(cog):
    """El embed muestra dinero, XP, trabajo y salud del perfil."""
    jugadores_repo.crear_jugador(111)
    jugadores_repo.actualizar_campos(
        111, {"dinero": 120, "experiencia": 8, "trabajo": "lavaplatos"}
    )
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "stats", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    embed = enviado["embed"]
    assert embed.title == "📊 Estadísticas - tester"
    campos = {f.name: f.value for f in embed.fields}
    assert campos["💰 Dinero"] == "$120"
    assert campos["🧾 Experiencia"] == "8"
    assert campos["💼 Trabajo"] == "Lavaplatos"  # nombre del catalogo, no el slug
    assert campos["❤️ Salud"] == "100 / 100"
    assert "ID: 111" in embed.footer.text


async def test_stats_sin_trabajo_muestra_texto_por_defecto(cog):
    """Sin trabajo asignado el campo lo dice claramente."""
    jugadores_repo.crear_jugador(222)
    inter = FabricaInteraccion.interaccion(user_id=222)

    await FabricaInteraccion.invocar(cog, "stats", inter)

    embed = inter.response.mensajes[0]["embed"]
    campo_trabajo = next(f for f in embed.fields if f.name == "💼 Trabajo")
    assert campo_trabajo.value == "Sin trabajo"


async def test_stats_con_enfermedad_marca_la_salud(cog):
    """Si el jugador esta enfermo la salud incluye el nombre de la dolencia."""
    jugadores_repo.crear_jugador(333)
    jugadores_repo.actualizar_campos(333, {"salud": 85, "enfermedad": "Gripe"})
    inter = FabricaInteraccion.interaccion(user_id=333)

    await FabricaInteraccion.invocar(cog, "stats", inter)

    embed = inter.response.mensajes[0]["embed"]
    campo_salud = next(f for f in embed.fields if f.name == "❤️ Salud")
    assert "85 / 100" in campo_salud.value
    assert "Gripe" in campo_salud.value


async def test_stats_trabajo_desaparecido_del_catalogo_usa_slug(cog):
    """Si el trabajo guardado ya no existe se muestra el slug crudo."""
    jugadores_repo.crear_jugador(444)
    jugadores_repo.actualizar_campo(444, "trabajo", "astronauta-fantasma")
    inter = FabricaInteraccion.interaccion(user_id=444)

    await FabricaInteraccion.invocar(cog, "stats", inter)

    embed = inter.response.mensajes[0]["embed"]
    campo_trabajo = next(f for f in embed.fields if f.name == "💼 Trabajo")
    assert campo_trabajo.value == "astronauta-fantasma"


async def test_stats_thumbnail_del_avatar(cog):
    """El embed lleva como miniatura el avatar del usuario fake."""
    jugadores_repo.crear_jugador(555)
    inter = FabricaInteraccion.interaccion(user_id=555)

    await FabricaInteraccion.invocar(cog, "stats", inter)

    embed = inter.response.mensajes[0]["embed"]
    assert embed.thumbnail.url == "https://example.com/avatar.png"
