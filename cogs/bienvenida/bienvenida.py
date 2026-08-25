"""Bienvenida a nuevos miembros en el canal configurado."""

import discord
from discord import app_commands
from discord.ext import commands

from database.servidor_repo import get_config, set_config


class Bienvenida(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setwelcome", description="Configura el canal de bienvenida.")
    @app_commands.describe(channel="Canal donde se anunciaran los nuevos miembros")
    @app_commands.default_permissions(administrator=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_config(interaction.guild.id, "welcome_channel_id", channel.id)
        await interaction.response.send_message(
            "Canal de bienvenida configurado en " + channel.mention, ephemeral=True
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        canal_id = get_config(member.guild.id, "welcome_channel_id")
        if not canal_id:
            return

        canal = member.guild.get_channel(canal_id)
        if canal is None:
            return

        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        embed = discord.Embed(
            title="Nuevo miembro",
            description="Bienvenido " + member.mention + " a **" + member.guild.name + "**",
            color=0x00FF88,
        )
        embed.set_thumbnail(url=avatar_url)

        await canal.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Bienvenida(bot))
