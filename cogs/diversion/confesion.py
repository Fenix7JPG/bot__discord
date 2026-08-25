"""Cog /confesion: publica una confesión anónima en el canal."""

import re

import discord
from discord import app_commands
from discord.ext import commands


class Confesion(commands.Cog):
    """Envia el embed de la confesion sin revelar al autor del comando."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="confesion", description="Envía una confesión anónima.")
    @app_commands.describe(mensaje="Tu confesión.", autor="Firma opcional de la confesión.")
    async def confesion(self, interaction: discord.Interaction, mensaje: str, autor: str = None):
        """Publica la confesion y confirma en privado al autor."""
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="💬 Nueva Confesión",
            description=mensaje,
            color=discord.Color.random(),
        )

        miembro_firmante = None
        if autor:
            # Si la firma es una mencion <@id> se resuelve el miembro real.
            match = re.search(r"\d{17,20}", autor)
            if match and interaction.guild is not None:
                try:
                    miembro_firmante = await interaction.guild.fetch_member(int(match.group(0)))
                except (discord.HTTPException, ValueError):
                    miembro_firmante = None

        if miembro_firmante is not None:
            embed.set_author(
                name=miembro_firmante.display_name,
                icon_url=miembro_firmante.display_avatar.url,
            )
            embed.set_footer(text="ID: " + str(miembro_firmante.id))
        elif autor:
            embed.set_footer(text="- " + autor)
        else:
            embed.set_footer(text="Autor anónimo 😶")

        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Confesión enviada correctamente (shhh 🤫)", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Confesion(bot))
