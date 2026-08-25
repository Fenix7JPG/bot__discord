"""Cog de dados: comandos /d6, /d10 y /d20."""

import random

import discord
from discord import app_commands
from discord.ext import commands


class Dados(commands.Cog):
    """Lanzamientos simples de dados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="d6", description="Lanza un dado de 6 caras 🎲")
    async def d6(self, interaction: discord.Interaction):
        resultado = random.randint(1, 6)
        await interaction.response.send_message("🎲 Has lanzado un **d6**: **" + str(resultado) + "**")

    @app_commands.command(name="d10", description="Lanza un dado de 10 caras 🎲")
    async def d10(self, interaction: discord.Interaction):
        resultado = random.randint(1, 10)
        await interaction.response.send_message("🎲 Has lanzado un **d10**: **" + str(resultado) + "**")

    @app_commands.command(name="d20", description="Lanza un dado de 20 caras 🎲")
    async def d20(self, interaction: discord.Interaction):
        resultado = random.randint(1, 20)
        await interaction.response.send_message("🎲 Has lanzado un **d20**: **" + str(resultado) + "**")


async def setup(bot: commands.Bot):
    await bot.add_cog(Dados(bot))
