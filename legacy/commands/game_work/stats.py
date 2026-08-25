# cogs/profile.py
import discord
from discord.ext import commands
from discord import app_commands

# --- IMPORTA TUS UTILIDADES ---
# Asegúrate de que esta ruta sea correcta según tu estructura de proyecto
from utils.data import load_data, PATH_USERS

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Muestra tus estadísticas: dinero, trabajo, experiencia y salud.")
    async def stats(self, interaction: discord.Interaction):
        """Muestra un embed con todas tus estadísticas personales."""
        # --- 1. Cargar solo los datos de usuarios ---
        data_users = await load_data(PATH_USERS)
        user_id = str(interaction.user.id)

        # --- 2. Verificar si existe el perfil ---
        if user_id not in data_users:
            await interaction.response.send_message(
                "❌ No tienes perfil creado. Usa el comando para crear tu perfil primero.",
                ephemeral=True
            )
            return

        user = data_users[user_id]

        # --- 3. Normalizar claves (soporta distintas estructuras) ---
        # CORRECCIÓN: Eliminé un paréntesis extra que había en el código original.
        try:
            dinero = int(user.get("dinero", user.get("money", 0)))
        except (ValueError, TypeError):
            dinero = 0

        trabajo_slug = user.get("trabajo") or user.get("job")  # puede ser None

        try:
            experiencia = int(user.get("experiencia", user.get("exp", 0)))
        except (ValueError, TypeError):
            experiencia = 0

        # Salud (soporta 'salud' o 'health')
        salud_raw = user.get("salud", user.get("health", 100))
        try:
            salud = int(salud_raw)
        except (ValueError, TypeError):
            salud = 100

        enfermedad = user.get("disease")  # nombre de la enfermedad si existe
        # date_disease = user.get("date_disease") # Esta variable no se usaba, la comento

        # --- 4. Preparar texto del trabajo (sin consultar jobs.json) ---
        if trabajo_slug:
            trabajo_display = f"`{trabajo_slug}`"
        else:
            trabajo_display = "Sin trabajo"

        # --- 5. Crear embed ---
        embed = discord.Embed(
            title=f"📊 Estadísticas — {interaction.user.display_name}",
            colour=discord.Colour.blurple()
        )
        embed.add_field(name="💰 Dinero", value=f"${dinero:,}", inline=True)
        embed.add_field(name="🧾 Experiencia", value=f"{experiencia:,}", inline=True)
        embed.add_field(name="💼 Trabajo", value=trabajo_display, inline=False)

        # Salud y posible enfermedad
        salud_value = f"{salud} / 100"
        if enfermedad:
            salud_value += f" — 🤒 **{enfermedad}**"
        embed.add_field(name="❤️ Salud", value=salud_value, inline=False)

        # Mini-avatar y footer con ID
        try:
            avatar_url = interaction.user.display_avatar.url
        except Exception:
            avatar_url = None

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"ID: {user_id}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))