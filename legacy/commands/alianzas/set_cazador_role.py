import discord
from discord import app_commands
from discord.ext import commands

from database.alianzas_repo import set_cazador_role


class SetCazadorRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Establecer rol de cazador
    @app_commands.command(name="setcazadorrol", description="Configura el rol de cazador")
    @app_commands.describe(role="Selecciona el rol de cazador")
    @app_commands.default_permissions(administrator=True)
    async def setcazadorrol(
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

        print("🔧 Configurando rol de cazador...")

        try:
            set_cazador_role(interaction.guild.id, role.id)

        except Exception as e:
            print(f"❌ Error al configurar rol de cazador: {e}")

            await interaction.response.send_message(
                "❌ Ocurrió un error al configurar el rol de cazador.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Rol de cazador configurado: {role.mention}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SetCazadorRole(bot))