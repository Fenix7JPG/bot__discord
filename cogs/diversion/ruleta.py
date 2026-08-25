"""Cog /ruleta: apostar a rojo, negro o cero en la ruleta europea."""

import random

import discord
from discord import app_commands
from discord.ext import commands

from database import jugadores_repo

NUMEROS_ROJOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


class Ruleta(commands.Cog):
    """Ruleta simple con pagos 1:1 para colores y 35:1 para el cero."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ruleta", description="Juega una ruleta.")
    @app_commands.describe(
        opcion="Apostar a rojo, negro o cero.",
        apuesta="Cantidad de dinero a apostar.",
    )
    async def ruleta(self, interaction: discord.Interaction, opcion: str, apuesta: int):
        """Gira la ruleta y liquida la apuesta en una sola escritura."""
        eleccion = str(opcion).strip().lower()
        if eleccion in ("rojo", "r", "red"):
            eleccion = "rojo"
        elif eleccion in ("negro", "n", "black"):
            eleccion = "negro"
        elif eleccion in ("0", "cero", "zero"):
            eleccion = "0"
        else:
            await interaction.response.send_message(
                "Opción inválida. Usa `rojo`, `negro` o `0`.", ephemeral=True
            )
            return

        if apuesta <= 0:
            await interaction.response.send_message(
                "La apuesta debe ser un entero mayor que 0.", ephemeral=True
            )
            return

        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

        dinero = int(jugador.get("dinero", 0) or 0)
        if dinero < apuesta:
            await interaction.response.send_message(
                "❌ No tienes suficiente dinero. Tu saldo: $" + str(dinero) + ".", ephemeral=True
            )
            return

        # Giro de la ruleta y color del numero.
        numero = random.randint(0, 36)
        if numero == 0:
            color = "0"
        elif numero in NUMEROS_ROJOS:
            color = "rojo"
        else:
            color = "negro"

        # Premio devuelto (apuesta incluida); 0 si se pierde.
        premio = 0
        if eleccion == "0":
            if numero == 0:
                premio = apuesta * 36  # paga 35:1
        elif color == eleccion:
            premio = apuesta * 2  # paga 1:1

        saldo_final = dinero - apuesta + premio
        jugadores_repo.actualizar_campo(interaction.user.id, "dinero", saldo_final)

        # Mensaje del resultado.
        if numero == 0:
            linea_resultado = "**0** - 🟢"
        else:
            emoji = "🔴" if color == "rojo" else "⚫"
            linea_resultado = "**" + str(numero) + "** - " + emoji + " " + color.capitalize()

        if premio > 0:
            ganancia_neta = premio - apuesta
            nota = "🎉 ¡Ganaste! Beneficio: **$" + str(ganancia_neta) + "**."
            if eleccion == "0":
                nota += " El cero paga 35:1."
        else:
            nota = "❌ Perdiste **$" + str(apuesta) + "**."

        embed = discord.Embed(title="🎰 Ruleta", colour=discord.Colour.dark_gold())
        embed.add_field(name="Resultado", value=linea_resultado, inline=False)
        embed.add_field(name="Tu apuesta", value=eleccion + " - $" + str(apuesta), inline=True)
        embed.add_field(name="Nota", value=nota, inline=True)
        embed.set_footer(
            text="Saldo actual: $" + str(saldo_final) + " - Jugador: " + interaction.user.display_name
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ruleta(bot))
