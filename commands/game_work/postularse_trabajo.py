# cogs/economy.py
import discord
from discord.ext import commands
from discord import app_commands
import random

# --- IMPORTA TUS UTILIDADES ---
# Asegúrate de que esta ruta sea correcta según tu estructura de proyecto
from utils.data import load_data, save_data, PATH_USERS, PATH_TRABAJOS

class PostularseTrabajo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="postularse-trabajo", description="Postúlate a un trabajo.")
    @app_commands.describe(
        trabajo="El nombre o el slug (identificador) del trabajo al que quieres postularte."
    )
    async def postularse_trabajo(self, interaction: discord.Interaction, trabajo: str):
        """Intenta conseguir un trabajo basado en tu experiencia."""
        # --- 1. Cargar datos ---
        data_users = await load_data(PATH_USERS)
        data_jobs = await load_data(PATH_TRABAJOS)
        user_id = str(interaction.user.id)

        # --- 2. Verificar perfil ---
        if user_id not in data_users:
            await interaction.response.send_message("❌ No tienes perfil creado. Usa el comando para crear tu perfil primero.", ephemeral=True)
            return

        # --- 3. Buscar el trabajo ---
        jobs_list = data_jobs.get("jobs", [])
        job = next(
            (j for j in jobs_list if j.get("slug") == trabajo or j.get("name", "").lower() == trabajo.lower()),
            None
        )

        if not job:
            # Mostrar ejemplos de slugs (los primeros 20 para no saturar)
            ejemplos = ", ".join(j.get("slug", "") for j in jobs_list[:20])
            await interaction.response.send_message(
                f"❌ El trabajo '{trabajo}' no existe. Asegúrate de usar el **slug** o el nombre completo.\n"
                f"Ejemplos de slugs: `{ejemplos}`",
                ephemeral=True
            )
            return

        # --- 4. Verificar si ya tiene el trabajo ---
        current_job_slug = data_users[user_id].get("job")
        if current_job_slug == job.get("slug"):
            await interaction.response.send_message(f"ℹ️ {interaction.user.mention}, ya trabajas como **{job.get('name')}**.", ephemeral=True)
            return

        # --- 5. Calcular la probabilidad y postular ---
        required_exp = int(job.get("required_experience", 0))
        user_exp = int(data_users[user_id].get("exp", 0))

        # Método simple de randomización
        if random.randint(0, required_exp) <= user_exp:
            # MEJORA: Guardamos el slug del trabajo para mantener consistencia
            data_users[user_id]["job"] = job.get("slug")
            await save_data(data_users, PATH_USERS)
            await interaction.response.send_message(f"✅ ¡Felicidades {interaction.user.mention}! Ahora trabajas como **{job.get('name')}**.")
        else:
            await interaction.response.send_message(f"❌ Lo siento {interaction.user.mention}, no fuiste aceptado para **{job.get('name')}**.")

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(PostularseTrabajo(bot))