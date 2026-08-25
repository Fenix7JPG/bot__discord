# cogs/economy.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime
from datetime import timezone, timedelta

# --- IMPORTA TUS UTILIDADES ---
from utils.data import load_data, save_data, PATH_USERS, PATH_TRABAJOS

class Curarse(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ... (otros comandos como postularse_trabajo y work) ...

    @app_commands.command(name="curarse", description="Cura tu salud gastando dinero.")
    @app_commands.describe(
        cantidad="La cantidad de vida que quieres curar. Si no especificas, curarás al máximo."
    )
    async def curarse(self, interaction: discord.Interaction, cantidad: int = 0):
        """Cura tu salud pagando una cantidad de dinero que aumenta con la cantidad curada."""
        user_id = str(interaction.user.id)
        data_users = await load_data(PATH_USERS)

        if user_id not in data_users:
            await interaction.response.send_message("❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True)
            return

        user = data_users[user_id]

        # Normalizar dinero y salud
        dinero_actual = int(user.get("dinero", user.get("money", 0) or 0))
        salud_actual = int(user.get("salud", 100))

        if salud_actual >= 100:
            await interaction.response.send_message("✅ Ya tienes la salud completa (100). No necesitas curarte.", ephemeral=True)
            return

        # --- MEJORA: Lógica para curar al máximo si no se especifica cantidad ---
        faltante = 100 - salud_actual
        if cantidad <= 0:
            # Si el usuario escribe /curarse sin número o con 0, cura al máximo
            heal_amount = faltante
        else:
            # Si especifica una cantidad, cura esa cantidad (sin pasar de 100)
            heal_amount = min(cantidad, faltante)

        # --- Fórmula de costo (sin cambios) ---
        base_cost_per_hp = 5
        scaling_quadratic = 0.20
        cost = int(heal_amount * base_cost_per_hp + (heal_amount ** 2) * scaling_quadratic)
        cost = max(1, cost)

        if dinero_actual < cost:
            await interaction.response.send_message(
                f"❌ No tienes suficiente dinero. Necesitas **${cost}**, tienes **${dinero_actual}**.",
                ephemeral=True
            )
            return

        # --- Aplicar curación y gasto ---
        user["salud"] = min(100, salud_actual + heal_amount)
        user["dinero"] = dinero_actual - cost

        # Si tenía una enfermedad y ahora tiene buena salud, limpiar la enfermedad
        if user.get("disease") and user.get("date_disease"):
            # criterio: si salud >= 80, consideramos que se recuperó de la enfermedad
            if user["salud"] >= 80:
                user.pop("disease", None)
                user.pop("date_disease", None)

        await save_data(data_users, PATH_USERS)

        await interaction.response.send_message(
            f"💊 {interaction.user.mention}, te curaste **{heal_amount}** de vida por **${cost}**.\n"
            f"🩺 Salud: **{salud_actual} → {user['salud']}** — Dinero restante: **${user['dinero']}**.",
            ephemeral=False
        )

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Curarse(bot))