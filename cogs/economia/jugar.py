"""Cog /jugar: registro del jugador para participar en la economia."""

import discord
from discord import app_commands
from discord.ext import commands

from database import jugadores_repo


class Jugar(commands.Cog):
    """Crea el perfil del usuario en la base de datos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="jugar", description="Registrate para jugar.")
    async def jugar(self, interaction: discord.Interaction):
        """Registra al usuario si aun no tiene perfil."""
        creado = jugadores_repo.crear_jugador(interaction.user.id)
        if creado:
            await interaction.response.send_message("¡Te has registrado! Usa /trabajos")
        else:
            await interaction.response.send_message("Ya estás registrado")


async def setup(bot: commands.Bot):
    await bot.add_cog(Jugar(bot))
