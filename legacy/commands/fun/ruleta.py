
# cogs/blackjack.py
import discord
import random
from discord.ext import commands
from discord import app_commands
# Asumo que esta importación es correcta según tu estructura de proyecto
from utils.data import load_data, PATH_USERS, save_data
class Ruleta(commands.Cog):
    def __init__(self,bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ruleta", description="Juega una ruleta")
    @app_commands.describe(
        opcion="Eliga una opcion",
        apuesta="Elige una cantidad para apostar."
    )
    async def ruleta(self,interaction: discord.Interaction, opcion: str, apuesta: int):
        """
        Ruleta simple: apostar a 'rojo', 'negro' o '0'.
        La apuesta se descuenta al inicio (como en blackjack). Los pagos:
        - rojo/negro: 1:1 (se añade apuesta*2 al ganar para devolver apuesta + ganancia)
        - 0: paga 35:1 (se añade apuesta*36 al ganar)
        """
        opcion_raw = str(opcion).strip().lower()
        # Normalizar opciones aceptadas
        if opcion_raw in ("rojo", "r", "red"):
            choice = "rojo"
        elif opcion_raw in ("negro", "n", "black", "blk"):
            choice = "negro"
        elif opcion_raw in ("0", "zero", "cero"):
            choice = "0"
        else:
            await interaction.response.send_message("Opción inválida. Usa `rojo`, `negro` o `0`.", ephemeral=True)
            return

        if apuesta is None or apuesta <= 0:
            await interaction.response.send_message("La apuesta debe ser un entero mayor que 0.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        data_users = await load_data(PATH_USERS)

        if user_id not in data_users:
            await interaction.response.send_message("❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True)
            return

        try:
            dinero_actual = int(data_users[user_id].get("dinero", data_users[user_id].get("money", 0) or 0))
        except Exception:
            dinero_actual = 0

        if dinero_actual < apuesta:
            await interaction.response.send_message(f"❌ No tienes suficiente dinero. Tu saldo: ${dinero_actual:,}.", ephemeral=True)
            return

        # Deduct bet immediately
        data_users[user_id]['dinero'] = dinero_actual - apuesta
        await save_data(data_users, PATH_USERS)

        # Ruleta: generar número 0-36 y determinar color
        import random
        number = random.randint(0, 36)
        # Números rojos en ruleta europea
        REDS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        if number == 0:
            color = "0"  # verde/zero
        elif number in REDS:
            color = "rojo"
        else:
            color = "negro"

        # Determinar resultado y pago
        won = False
        amount_won = 0
        if choice == "0":
            if number == 0:
                # paga 35:1  -> devolvemos apuesta + 35*apuesta = apuesta * 36
                amount_won = apuesta * 36
                won = True
        else:
            if color == choice:
                # paga 1:1 -> devolvemos apuesta + ganancia = apuesta * 2
                amount_won = apuesta * 2
                won = True

        # Actualizar dinero en archivo
        latest = await load_data(PATH_USERS)
        latest.setdefault(user_id, {})
        latest[user_id]['dinero'] = int(latest[user_id].get('dinero', 0)) + (amount_won if won else 0)
        await save_data(latest, PATH_USERS)

        saldo_final = latest[user_id]['dinero']

        # Preparar mensaje
        from discord import Embed
        if number == 0:
            result_line = f"**0** — 🟢"
        else:
            emoji = "🔴" if color == "rojo" else "⚫"
            result_line = f"**{number}** — {emoji} {color.capitalize()}"

        if won:
            if choice == "0":
                note = f"🎉 ¡Ha salido 0! Apuestas a **0** y ganas **${amount_won - apuesta:,}** (pago 35:1)."
            else:
                note = f"🎉 ¡Ganaste! Salió **{number} ({color})**. Ganancia: **${amount_won - apuesta:,}**."
        else:
            note = f"❌ Perdiste. Salió **{number} ({color})**. Perdida: **${apuesta:,}**."

        embed = Embed(title="🎰 Ruleta", colour=discord.Colour.dark_gold())
        embed.add_field(name="Resultado", value=result_line, inline=False)
        embed.add_field(name="Apuesta", value=f"{choice} — ${apuesta:,}", inline=True)
        embed.add_field(name="Resultado", value=note, inline=True)
        embed.set_footer(text=f"Saldo actual: ${saldo_final:,} — Jugador: {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed, ephemeral=False)

# --- FUNCIÓN DE CONFIGURACIÓN DEL COG ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Ruleta(bot))