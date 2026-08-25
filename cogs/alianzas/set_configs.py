"""Comandos de configuracion de alianzas (solo administradores)."""

import discord
from discord import app_commands
from discord.ext import commands

from database.servidor_repo import set_config


class SetConfigs(commands.Cog):
    """Guarda canal y roles que usa el sistema de alianzas."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setalianzachannel", description="Configura el canal de alianzas.")
    @app_commands.describe(channel="Canal donde se registraran las alianzas")
    @app_commands.default_permissions(administrator=True)
    async def setalianzachannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
            return
        set_config(interaction.guild.id, "alliance_channel_id", channel.id)
        await interaction.response.send_message("Canal de alianzas configurado en " + channel.mention, ephemeral=True)

    @app_commands.command(name="setalianzarol", description="Configura el rol de alianza.")
    @app_commands.describe(role="Rol que se otorga por alianzas")
    @app_commands.default_permissions(administrator=True)
    async def setalianzarol(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
            return
        set_config(interaction.guild.id, "alliance_role_id", role.id)
        await interaction.response.send_message("Rol de alianza configurado: " + role.mention, ephemeral=True)

    @app_commands.command(name="setcazadorrol", description="Configura el rol de cazador.")
    @app_commands.describe(role="Rol necesario para registrar alianzas")
    @app_commands.default_permissions(administrator=True)
    async def setcazadorrol(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
            return
        set_config(interaction.guild.id, "hunter_role_id", role.id)
        await interaction.response.send_message("Rol de cazador configurado: " + role.mention, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SetConfigs(bot))
