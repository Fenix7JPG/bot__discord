"""Cog /curarse: recuperar salud pagando dinero."""

import discord
from discord import app_commands
from discord.ext import commands

from database import jugadores_repo

SALUD_MAXIMA = 100
COSTO_POR_VIDA = 5
ESCALADO_CUADRATICO = 0.20
SALUD_PARA_LIMPIAR_ENFERMEDAD = 80


class Curarse(commands.Cog):
    """Cura la salud del jugador con un costo que crece de forma cuadratica."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="curarse", description="Cura tu salud gastando dinero.")
    @app_commands.describe(cantidad="Vida a curar. Si no la indicas, te curas todo lo que falte.")
    async def curarse(self, interaction: discord.Interaction, cantidad: int = 0):
        """Calcula el costo, valida el dinero y aplica la curacion."""
        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

        dinero = int(jugador.get("dinero", 0) or 0)
        salud = int(jugador.get("salud", SALUD_MAXIMA) or 0)

        if salud >= SALUD_MAXIMA:
            await interaction.response.send_message(
                "✅ Ya tienes la salud completa (" + str(SALUD_MAXIMA) + "). No necesitas curarte.",
                ephemeral=True,
            )
            return

        faltante = SALUD_MAXIMA - salud
        if cantidad <= 0:
            vida_a_curar = faltante
        else:
            vida_a_curar = min(cantidad, faltante)

        costo = int(vida_a_curar * COSTO_POR_VIDA + (vida_a_curar ** 2) * ESCALADO_CUADRATICO)
        costo = max(1, costo)

        if dinero < costo:
            await interaction.response.send_message(
                "❌ No tienes suficiente dinero. Necesitas **$"
                + str(costo)
                + "** y tienes **$"
                + str(dinero)
                + "**.",
                ephemeral=True,
            )
            return

        nueva_salud = salud + vida_a_curar
        campos = {"salud": nueva_salud, "dinero": dinero - costo}

        # Con buena salud se considera superada la enfermedad.
        if jugador.get("enfermedad") and nueva_salud >= SALUD_PARA_LIMPIAR_ENFERMEDAD:
            campos["enfermedad"] = None
            campos["fecha_enfermedad"] = None

        jugadores_repo.actualizar_campos(jugador["user_id"], campos)

        await interaction.response.send_message(
            "💊 "
            + interaction.user.mention
            + ", te curaste **"
            + str(vida_a_curar)
            + "** de vida por **$"
            + str(costo)
            + "**.\n🩺 Salud: **"
            + str(salud)
            + " -> "
            + str(nueva_salud)
            + "** - Dinero restante: **$"
            + str(campos["dinero"])
            + "**."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Curarse(bot))
