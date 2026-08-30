"""Cog /renunciar-trabajo: dejar la profesion actual con confirmacion."""

import discord
from discord import app_commands
from discord.ext import commands

from cogs.economia.vistas_trabajo import vista_confirmar_renuncia
from database import jugadores_repo
from utils import datos


class RenunciarTrabajo(commands.Cog):
    """Permite al jugador abandonar su profesion actual."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="renunciar-trabajo",
        description="Renuncia a tu trabajo actual.",
    )
    async def renunciar_trabajo(self, interaction: discord.Interaction):
        """Pide confirmacion antes de borrar la profesion del perfil."""
        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

        slug = jugador.get("trabajo")
        if not slug:
            await interaction.response.send_message(
                "❌ No tienes ninguna profesion de la que renunciar.", ephemeral=True
            )
            return

        job = datos.buscar_trabajo(slug)
        nombre = str(job.get("name")) if job else str(slug)

        vista = vista_confirmar_renuncia(self, interaction.user.id)
        await interaction.response.send_message(
            "Vas a renunciar a tu profesion de **"
            + nombre
            + "**. No perderas tu dinero ni tu experiencia, pero tendras que"
            + " postularte de nuevo para volver a trabajar.\n"
            + "Confirmas tu renuncia?",
            view=vista,
        )

    async def procesar_confirmacion(self, interaction: discord.Interaction, confirmo: bool):
        """Aplica la decision del dueno de la confirmacion."""
        if not confirmo:
            await interaction.response.edit_message(
                content="Perfecto, seguis con tu profesion actual.", view=None
            )
            return

        jugadores_repo.actualizar_campo(interaction.user.id, "trabajo", None)
        await interaction.response.edit_message(
            content="Renunciaste a tu profesion. Usa /trabajos y /postularse-trabajo"
            + " cuando quieras volver al ruedo.",
            view=None,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RenunciarTrabajo(bot))
