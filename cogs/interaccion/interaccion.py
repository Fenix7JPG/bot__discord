"""Interacciones sociales con GIFs: /interact pat y /interact punch."""

import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


API_BASE = "https://nekos.best/api/v2/"


class Interaccion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session is not None:
            await self.session.close()

    async def obtener_gif(self, tipo: str) -> dict | None:
        """Pide un GIF a nekos.best. Devuelve url y anime o None si fallo."""
        if self.session is None:
            return None
        try:
            async with self.session.get(API_BASE + tipo, timeout=10) as respuesta:
                if respuesta.status != 200:
                    return None
                datos = await respuesta.json()
                resultados = datos.get("results") or []
                if not resultados:
                    return None
                primero = resultados[0]
                return {"url": primero.get("url"), "anime": primero.get("anime_name")}
        except Exception:
            return None

    # Grupo de comandos /interact
    grupo = app_commands.Group(name="interact", description="Interactua con alguien")

    @grupo.command(name="pat", description="Da una caricia a alguien.")
    @app_commands.describe(user="Usuario al que acaricias")
    async def pat(self, interaction: discord.Interaction, user: discord.Member):
        gif = await self.obtener_gif("pat")
        if gif is None or not gif.get("url"):
            await interaction.response.send_message("No pude conseguir un GIF, intenta de nuevo.", ephemeral=True)
            return

        if user.id == interaction.user.id:
            titulo = interaction.user.display_name + " se acaricia a si mismo"
            descripcion = None
        else:
            titulo = interaction.user.display_name + " acaricia a " + user.display_name
            caricias = random.randint(5, 20)
            descripcion = user.display_name + " ha recibido **" + str(caricias) + "** caricias."

        embed = discord.Embed(title=titulo, description=descripcion, color=discord.Color.purple())
        embed.set_image(url=gif["url"])
        if gif.get("anime"):
            embed.set_footer(text="Anime: " + gif["anime"])
        await interaction.response.send_message(embed=embed)

    @grupo.command(name="punch", description="Dale un golpe a alguien.")
    @app_commands.describe(user="Usuario al que golpeas")
    async def punch(self, interaction: discord.Interaction, user: discord.Member):
        gif = await self.obtener_gif("punch")
        if gif is None or not gif.get("url"):
            await interaction.response.send_message("No pude conseguir un GIF, intenta de nuevo.", ephemeral=True)
            return

        if user.id == interaction.user.id:
            titulo = interaction.user.display_name + " se golpea a si mismo"
            descripcion = None
        else:
            titulo = interaction.user.display_name + " golpeo a " + user.display_name
            golpes = random.randint(1, 10)
            descripcion = user.display_name + " recibio **" + str(golpes) + "** golpes."

        embed = discord.Embed(title=titulo, description=descripcion, color=discord.Color.red())
        embed.set_image(url=gif["url"])
        if gif.get("anime"):
            embed.set_footer(text="Anime: " + gif["anime"])
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Interaccion(bot))
