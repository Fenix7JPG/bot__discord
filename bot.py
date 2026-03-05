# bot.py
import discord
from discord.ext import commands
import os
import asyncio  # Importamos asyncio para manejar el bucle de eventos
from pathlib import Path  # Importamos pathlib para manejar rutas de forma robusta

from webserver import keep_alive
keep_alive()

from database.database import _setup
_setup()  # Aseguramos que la base de datos esté configurada antes de iniciar el bot
# --- Configuración del Bot ---
intents = discord.Intents.default()
intents.message_content = True # Necesario para leer el contenido de los mensajes
intents.members = True  # Necesario para detectar cuando un miembro se une
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    await bot.tree.sync() # Sincroniza los comandos de barra
    print('🔁 Comandos de barra sincronizados.')
    print('------')

# --- Función asíncrona para cargar Cogs ---
async def load_cogs():
    """Busca y carga todos los Cogs en la carpeta 'commands'."""
    # Usamos pathlib para encontrar todos los archivos .py de forma recursiva
    # rglob('*.py') busca en 'commands' y todas sus subcarpetas
    for filepath in Path('./commands').rglob('*.py'):
        # Ignoramos el archivo __init__.py
        if filepath.name == '__init__.py':
            continue

        # Convertimos la ruta del archivo a un formato de módulo importable
        # Ejemplo: commands/utils/ping.py -> commands.utils.ping
        module_path = '.'.join(filepath.parts[:-1] + (filepath.stem,))
        
        try:
            # Ahora SÍ podemos usar await porque estamos en una función async
            await bot.load_extension(module_path)
            print(f'📦 Cargado: {module_path}')
        except Exception as e:
            print(f'❌ No se pudo cargar el cog {module_path} debido a: {e}')

# --- Función principal asíncrona ---
async def main():
    async with bot:
        await load_cogs()  # Cargamos los cogs antes de iniciar el bot
        DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
        await bot.start(DISCORD_TOKEN)

# --- Punto de entrada del script ---
# Ejecutamos la función main usando asyncio.run()
if __name__ == "__main__":
    asyncio.run(main())