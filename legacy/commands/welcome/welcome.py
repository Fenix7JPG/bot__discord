import discord
from discord.ext import commands
from discord import app_commands

from database.welcome_repo import set_welcome_channel, get_welcome_channel


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setwelcome", description="Configura el canal de bienvenida")
    async def setwelcome(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        print("🔧 Configurando canal de bienvenida...")
        try:
            set_welcome_channel(interaction.guild.id, channel.id)
        except Exception as e:
            print(f"❌ Error al configurar el canal de bienvenida: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al configurar el canal de bienvenida. Por favor, inténtalo de nuevo.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Canal de bienvenida configurado en {channel.mention}",
            ephemeral=True  # solo lo ve el admin
        )

    # Evento cuando alguien entra
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel_id = get_welcome_channel(member.guild.id)

        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)

        if not channel:
            return

        embed = discord.Embed(
            title="🎉 ¡Nuevo miembro!",
            description=f"Bienvenido {member.mention} a **{member.guild.name}**",
            color=0x00ff88
        )

        embed.set_thumbnail(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))