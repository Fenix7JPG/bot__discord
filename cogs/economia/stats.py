"""Cog /stats: estadisticas del jugador en un embed efimero."""

import discord
from discord import app_commands
from discord.ext import commands

from database import jugadores_repo
from utils import datos


class Stats(commands.Cog):
    """Muestra dinero, experiencia, trabajo y salud del jugador."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="stats", description="Muestra tus estadisticas: dinero, trabajo, experiencia y salud."
    )
    async def stats(self, interaction: discord.Interaction):
        """Arma el embed con el perfil actual del usuario."""
        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

        dinero = int(jugador.get("dinero", 0) or 0)
        experiencia = int(jugador.get("experiencia", 0) or 0)
        salud = int(jugador.get("salud", 100) or 0)

        slug = jugador.get("trabajo")
        if slug:
            job = datos.buscar_trabajo(slug)
            trabajo_texto = str(job.get("name")) if job else str(slug)
        else:
            trabajo_texto = "Sin trabajo"

        salud_texto = str(salud) + " / 100"
        enfermedad = jugador.get("enfermedad")
        if enfermedad:
            salud_texto += " - 🤒 **" + str(enfermedad) + "**"

        embed = discord.Embed(
            title="📊 Estadísticas - " + interaction.user.display_name,
            colour=discord.Colour.blurple(),
        )
        embed.add_field(name="💰 Dinero", value="$" + str(dinero), inline=True)
        embed.add_field(name="🧾 Experiencia", value=str(experiencia), inline=True)
        embed.add_field(name="💼 Trabajo", value=trabajo_texto, inline=False)
        embed.add_field(name="❤️ Salud", value=salud_texto, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="ID: " + str(interaction.user.id))

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
