"""Cog /cat: envia una imagen de gato al azar.

Consulta varias APIs publicas en orden; si una falla prueba la siguiente.
"""

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


# Cada entrada es (url, extractor). El extractor saca la URL de la imagen
# desde la respuesta JSON de cada API.
FUENTES = [
    ("https://api.thecatapi.com/v1/images/search", lambda datos: datos[0]["url"]),
    ("https://aws.random.cat/meow", lambda datos: datos["file"]),
    ("https://cataas.com/cat?json=true", lambda datos: "https://cataas.com" + datos["url"]),
]


class Cat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session is not None:
            await self.session.close()

    async def obtener_gato(self) -> str | None:
        """Devuelve la URL de la imagen del primer servicio que responda."""
        if self.session is None:
            return None

        for url_api, extraer in FUENTES:
            try:
                async with self.session.get(url_api, timeout=10) as respuesta:
                    if respuesta.status != 200:
                        continue
                    datos = await respuesta.json()
                    imagen = extraer(datos)
                    if imagen:
                        return imagen
            except Exception:
                continue  # siguiente fuente
        return None

    @app_commands.command(name="cat", description="Envia una imagen de gato al azar.")
    async def cat(self, interaction: discord.Interaction):
        await interaction.response.defer()  # evitar timeout mientras buscamos

        url_imagen = await self.obtener_gato()
        if not url_imagen:
            await interaction.followup.send(
                "No pude conseguir un gatito ahora mismo, intenta mas tarde."
            )
            return

        embed = discord.Embed(color=0xF5A9B8)
        embed.set_image(url=url_imagen)
        embed.set_footer(text="Miau")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Cat(bot))
