"""Diagnostico del comando /cat: prueba las 3 fuentes una por una.

Uso: python scripts/probar_cat.py
Muestra que responde cada API y la imagen final que enviaria el bot.
"""

import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import aiohttp  # noqa: E402

from cogs.diversion.cat import FUENTES, TIMEOUT_POR_FUENTE  # noqa: E402


async def main():
    async with aiohttp.ClientSession() as session:
        for url_api, extraer in FUENTES:
            print("Probando:", url_api)
            try:
                async with session.get(url_api, timeout=TIMEOUT_POR_FUENTE) as respuesta:
                    print("   HTTP", respuesta.status)
                    if respuesta.status != 200:
                        continue
                    datos = await respuesta.json()
                    print("   JSON crudo:", str(datos)[:160])
                    try:
                        imagen = extraer(datos)
                        print("   IMAGEN extraida:", imagen)
                    except Exception as e:
                        print("   ERROR extrayendo:", type(e).__name__, str(e)[:100])
            except Exception as e:
                print("   FALLO peticion:", type(e).__name__, str(e)[:100])
            print("")


if __name__ == "__main__":
    asyncio.run(main())
