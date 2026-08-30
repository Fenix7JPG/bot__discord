"""Cog /postularse-trabajo: solicitar un trabajo segun la experiencia.

La probabilidad de entrar sin cumplir requisitos es configurable por
servidor (server_economy_config.lucky_chance, editable desde el dashboard).
"""

import random

import discord
from discord import app_commands
from discord.ext import commands

from database import jugadores_repo, servidor_repo
from utils import datos


class PostularseTrabajo(commands.Cog):
    """Permite al jugador postularse a un trabajo de la lista."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="postularse-trabajo", description="Postúlate a un trabajo.")
    @app_commands.describe(trabajo="Nombre o slug del trabajo al que quieres postularte.")
    async def postularse_trabajo(self, interaction: discord.Interaction, trabajo: str):
        """Busca el trabajo y decide si el jugador es aceptado."""
        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

        job = datos.buscar_trabajo(trabajo)
        if job is None:
            ejemplos = ", ".join(str(j.get("slug", "")) for j in datos.obtener_trabajos()[:10])
            await interaction.response.send_message(
                "❌ El trabajo '" + trabajo + "' no existe. Usa el **slug** o el nombre completo.\n"
                "Ejemplos de slugs: `" + ejemplos + "`",
                ephemeral=True,
            )
            return

        slug = str(job.get("slug") or job.get("name") or "")
        if jugador.get("trabajo") == slug:
            await interaction.response.send_message(
                "ℹ️ Ya trabajas como **" + str(job.get("name")) + "**.", ephemeral=True
            )
            return

        # Probabilidad de entrada sin requisitos: config del servidor (DM = default)
        if interaction.guild is not None:
            config = servidor_repo.get_economia(interaction.guild.id)
        else:
            config = dict(servidor_repo.ECONOMIA_DEFAULTS)
        probabilidad = int(config.get("lucky_chance", 30) or 0) / 100.0

        requerida = datos.experiencia_requerida(job)
        experiencia = int(jugador.get("experiencia", 0) or 0)

        # Con la XP suficiente entra siempre; si no, hay tirada de suerte.
        if experiencia >= requerida:
            aceptado = True
            detalle = "Cumples la experiencia requerida."
        else:
            aceptado = random.random() < probabilidad
            detalle = (
                "Entraste con suerte (probabilidad del servidor: "
                + str(int(config.get("lucky_chance", 30) or 0))
                + "%)."
                if aceptado
                else ""
            )

        if not aceptado:
            await interaction.response.send_message(
                "❌ No te aceptaron para **"
                + str(job.get("name"))
                + "**.\nTu experiencia: **"
                + str(experiencia)
                + " XP** - Requerida: **"
                + str(requerida)
                + " XP**. Sigue trabajando e inténtalo de nuevo.\n"
                + "Probabilidad de entrada sin requisitos en este servidor: **"
                + str(int(config.get("lucky_chance", 30) or 0))
                + "%**.",
                ephemeral=True,
            )
            return

        jugadores_repo.actualizar_campo(interaction.user.id, "trabajo", slug)
        mensaje = (
            "✅ ¡Felicidades "
            + interaction.user.mention
            + "! Ahora trabajas como **"
            + str(job.get("name"))
            + "**.\nTu experiencia: **"
            + str(experiencia)
            + " XP** - Requerida: **"
            + str(requerida)
            + " XP**."
        )
        if detalle:
            mensaje += "\n" + detalle
        await interaction.response.send_message(mensaje)


async def setup(bot: commands.Bot):
    await bot.add_cog(PostularseTrabajo(bot))
