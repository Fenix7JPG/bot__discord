"""Punto de entrada del bot.

- Configura intents y sincroniza comandos de barra al conectar.
- Carga automáticamente todos los cogs dentro de cogs/ (recursivo).
- Levanta el webserver de keep-alive para Render.

Uso: python bot.py  (requiere DISCORD_TOKEN en el entorno o en .env)
"""

import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from config import settings
from database.database import db
from webserver import instalar_captura_logs, keep_alive


def construir_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True   # leer mensajes (IA por mención, ruleta rusa)
    intents.members = True           # detectar entradas de miembros (bienvenida)
    intents.voice_states = True      # música y radio
    return commands.Bot(command_prefix="!", intents=intents)


bot = construir_bot()


@bot.event
async def on_ready():
    print("Bot conectado como", bot.user)
    await bot.tree.sync()
    print("Comandos de barra sincronizados.")


async def load_cogs():
    """Carga todos los archivos .py de cogs/ como extensiones."""
    for filepath in Path("./cogs").rglob("*.py"):
        if filepath.name == "__init__.py":
            continue
        module_path = ".".join(filepath.parts[:-1] + (filepath.stem,))
        try:
            await bot.load_extension(module_path)
            print("Cog cargado:", module_path)
        except Exception as e:
            print("No se pudo cargar el cog", module_path, ":", e)


async def main():
    instalar_captura_logs()  # capturar prints/logs para el visor /terminal
    db.setup()  # crear tablas antes de que los cogs pidan datos
    keep_alive()
    print("Iniciando bot; modo de BD:", db.mode)
    async with bot:
        await load_cogs()
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
