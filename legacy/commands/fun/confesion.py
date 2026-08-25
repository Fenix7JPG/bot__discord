import discord
from discord.ext import commands
from discord import app_commands
import re

class Confesion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="confesion", description="Envía una confesión anónima")
    @app_commands.describe(
        mensaje="Tu confesion",
        autor="Si deseas"
    )
    async def confesion(self,interaction: discord.Interaction, mensaje: str, autor: str = None):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="💬 Nueva Confesión",
            description=mensaje,
            color=discord.Color.random()
        )

        user_fake = None

        if autor:
            # Limpia el autor si es mención tipo <@123> o <@!123>
            match = re.search(r"\d{17,20}", autor)
            if match:
                user_id = int(match.group(0))
                try:
                    user_fake = await interaction.guild.fetch_member(user_id)
                except:
                    user_fake = None

        # Mostrar según el tipo de autor
        if user_fake:
            embed.set_author(name=user_fake.display_name, icon_url=user_fake.display_avatar.url)
            embed.set_footer(text=f"ID: {user_fake.id}")
        elif autor:
            embed.set_footer(text=f"— {autor}")
        else:
            embed.set_footer(text="Autor anónimo 😶")

        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Confesión enviada correctamente (shhh 🤫)", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Confesion(bot))