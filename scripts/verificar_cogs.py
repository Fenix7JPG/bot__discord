"""Carga real de todos los cogs con el bot de Discord en modo simulado.

Verifica que cada extension importa, define setup() y se agrega al bot
sin errores. No se conecta a Discord: solo carga las extensiones.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import discord  # noqa: E402
from discord.ext import commands  # noqa: E402


async def main():
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

    cargados = []
    fallos = []

    for ruta in sorted(Path("./cogs").rglob("*.py")):
        if ruta.name == "__init__.py":
            continue
        modulo = ".".join(ruta.parts[:-1] + (ruta.stem,))
        try:
            await bot.load_extension(modulo)
            cargados.append(modulo)
        except Exception as e:
            fallos.append((modulo, repr(e)))

    print("Cargados:", len(cargados))
    for m in cargados:
        print("  OK", m)
    if fallos:
        print("FALLOS:", len(fallos))
        for m, e in fallos:
            print("  X", m, "->", e)
        sys.exit(1)
    else:
        print("TODOS LOS COGS CARGAN CORRECTAMENTE")


if __name__ == "__main__":
    asyncio.run(main())
