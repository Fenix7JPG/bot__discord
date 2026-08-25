"""Comandos utilitarios basicos."""

import discord
from discord import app_commands
from discord.ext import commands


class Utilidades(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Muestra la latencia del bot.")
    async def ping(self, interaction: discord.Interaction):
        latencia = round(self.bot.latency * 1000)
        await interaction.response.send_message("Pong! Latencia: " + str(latencia) + "ms")

    @app_commands.command(name="eco", description="Repite tu mensaje.")
    @app_commands.describe(mensaje="Texto a repetir")
    async def eco(self, interaction: discord.Interaction, mensaje: str):
        await interaction.response.send_message(mensaje)


async def setup(bot):
    await bot.add_cog(Utilidades(bot))
