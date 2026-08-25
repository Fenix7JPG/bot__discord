import discord
from discord import app_commands
from discord.ext import commands

from database.alianzas_repo import set_alianza_role


class SetAlianzaRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Establecer rol de alianza
    @app_commands.command(name="setalianzarol", description="Configura el rol de alianza")
    @app_commands.describe(role="Selecciona el rol de alianza")
    @app_commands.default_permissions(administrator=True)
    async def setalianzarol(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Este comando solo funciona en servidores.",
                ephemeral=True
            )
            return

        print("🔧 Configurando rol de alianza...")

        try:
            set_alianza_role(interaction.guild.id, role.id)

        except Exception as e:
            print(f"❌ Error al configurar el rol de alianza: {e}")

            await interaction.response.send_message(
                "❌ Ocurrió un error al configurar el rol de alianza.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Rol de alianza configurado: {role.mention}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SetAlianzaRole(bot))