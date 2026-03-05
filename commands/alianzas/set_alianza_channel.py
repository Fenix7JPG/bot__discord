import discord
from discord import app_commands
from discord.ext import commands

from database.alianzas_repo import set_alianza_channel



class SetAlianzaChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Establecer canal de alianzas
    @app_commands.command(name="setalianzachannel", description="Configura el canal de alianzas")
    @app_commands.describe(channel="Selecciona el canal de alianzas")
    @app_commands.default_permissions(administrator=True)
    async def setalianzachannel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Este comando solo funciona en servidores.",
                ephemeral=True
            )
            return

        print("🔧 Configurando canal de alianzas...")
        try:
            set_alianza_channel(interaction.guild.id, channel.id)
        except Exception as e:
            print(f"❌ Error al configurar el canal de alianzas: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al configurar el canal de alianzas. Por favor, inténtalo de nuevo.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Canal de alianzas configurado en {channel.mention}",
            ephemeral=True  # solo lo ve el admin
        )
async def setup(bot):
    await bot.add_cog(SetAlianzaChannel(bot))