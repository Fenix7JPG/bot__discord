# cogs/economy.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime
from datetime import timezone, timedelta

# --- IMPORTA TUS UTILIDADES ---
from ...utils.data import load_data, save_data, PATH_USERS, PATH_TRABAJOS

class Work(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ... (otros comandos como postularse_trabajo) ...

    @app_commands.command(name="work", description="Trabaja para ganar dinero y experiencia (requiere tener un trabajo).")
    async def work(self, interaction: discord.Interaction):
        """
        Trabaja para ganar dinero y experiencia. Depende de `date_job`:
        - Si no han pasado 24h, hay riesgo de enfermedad.
        - Si han pasado 24h, ganas dinero y XP normales.
        """
        # --- 1. Verificaciones iniciales ---
        user_id = str(interaction.user.id)
        data_users = await load_data(PATH_USERS)

        if user_id not in data_users:
            await interaction.response.send_message("❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True)
            return

        user = data_users[user_id]
        trabajo_slug = user.get("trabajo") or user.get("job")
        if not trabajo_slug:
            await interaction.response.send_message("❌ No tienes un trabajo asignado. Usa /postularse-trabajo para conseguir uno.", ephemeral=True)
            return

        # --- 2. Cargar información del trabajo ---
        data_jobs = await load_data(PATH_TRABAJOS)
        raw_jobs = data_jobs.get("jobs") if isinstance(data_jobs, dict) else data_jobs
        jobs_list = raw_jobs or []

        job = None
        if isinstance(jobs_list, dict):
            job = jobs_list.get(trabajo_slug)
        if not job and isinstance(jobs_list, list):
            job = next((j for j in jobs_list if (j.get("slug") == trabajo_slug or j.get("name", "").lower() == str(trabajo_slug).lower())), None)

        required_exp = 0
        base_pay = None
        if job:
            try:
                required_exp = int(job.get("required_experience", job.get("required", 0) or 0))
            except (ValueError, TypeError):
                required_exp = 0
            for key in ("salary", "pay", "income", "wage", "salary_per_day", "pago", "sueldo"):
                if job.get(key) is not None:
                    try:
                        base_pay = int(job.get(key))
                        break
                    except (ValueError, TypeError):
                        pass

        if base_pay is None:
            base_pay = 50 + (required_exp * 10) + random.randint(0, 100)
        xp_gain = random.randint(5, 20) + (required_exp // 2)

        # --- 3. Lógica del cooldown de 24 horas ---
        now = datetime.datetime.now(tz=timezone.utc)
        last_work_iso = user.get("date_job")
        last_work_dt = None
        if last_work_iso:
            try:
                last_work_dt = datetime.datetime.fromisoformat(last_work_iso)
                if last_work_dt.tzinfo is None:
                    last_work_dt = last_work_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                last_work_dt = None

        allow_normal = True
        hours_since = None
        if last_work_dt:
            delta = now - last_work_dt
            hours_since = delta.total_seconds() / 3600.0
            if hours_since < 24:
                allow_normal = False

        # --- 4. Rama: No han pasado 24h (riesgo de enfermedad) ---
        if not allow_normal:
            hazard = max(5, min(45, int((24 - hours_since) * (45 / 24)))) # CORRECCIÓN: Paréntesis extra eliminado
            roll = random.randint(1, 100)
            if roll <= hazard:
                diseases = [
                    {"name": "resfriado", "damage": random.randint(5, 12)},
                    {"name": "gripe", "damage": random.randint(8, 20)},
                    {"name": "intoxicación alimentaria", "damage": random.randint(6, 18)},
                    {"name": "fiebre", "damage": random.randint(7, 15)},
                    {"name": "fatiga severa", "damage": random.randint(5, 14)}
                ]
                chosen = random.choice(diseases)
                current_health = int(user.get("salud", 100))
                new_health = max(0, current_health - chosen["damage"])
                user["salud"] = new_health
                user["disease"] = chosen["name"]
                user["date_disease"] = now.isoformat()
                
                dinero_actual = int(user.get("dinero", user.get("money", 0) or 0))
                # CORRECCIÓN: Paréntesis extra eliminado
                gasto_med = min(dinero_actual, random.randint(0, max(0, int(dinero_actual * 0.1))))
                user["dinero"] = dinero_actual - gasto_med
                user["date_job"] = now.isoformat()
                xp_earned = max(1, xp_gain // 4)
                user["experiencia"] = int(user.get("experiencia", user.get("exp", 0) or 0)) + xp_earned

                await save_data(data_users, PATH_USERS)
                await interaction.response.send_message(
                    f"🤒 Oh no — trabajaste demasiado pronto ({hours_since:.1f}h desde el último /work). "
                    f"Te contagiaste de **{chosen['name']}** y perdiste **{chosen['damage']}** de salud.\n"
                    f"Gastaste ${gasto_med} en atención y obtuviste solo {xp_earned} XP.\n"
                    f"Salud actual: **{new_health}**.\n"
                    f"🔸 Consejo: espera 24 horas entre trabajos para evitar este riesgo.",
                    ephemeral=False
                )
                return
            else:
                pay = max(1, base_pay // 2)
                user["dinero"] = int(user.get("dinero", user.get("money", 0) or 0)) + pay
                gained_xp = max(1, xp_gain // 2)
                user["experiencia"] = int(user.get("experiencia", user.get("exp", 0) or 0)) + gained_xp
                user["date_job"] = now.isoformat()
                await save_data(data_users, PATH_USERS)
                await interaction.response.send_message(
                    f"💼 Trabajaste pero aún no pasaron 24 horas desde tu último /work ({hours_since:.1f}h). "
                    f"Tu pago se vio reducido por cansancio: **${pay}** y ganaste **{gained_xp} XP**.\n"
                    f"🔸 Riesgo de enfermedad en este intento: **{hazard}%**. ¡Ten cuidado!",
                    ephemeral=False
                )
                return

        # --- 5. Rama: Han pasado 24h o es el primer trabajo ---
        variability = random.uniform(0.9, 1.3)
        pay = max(1, int(base_pay * variability))
        user["dinero"] = int(user.get("dinero", user.get("money", 0) or 0)) + pay
        user["experiencia"] = int(user.get("experiencia", user.get("exp", 0) or 0)) + xp_gain
        user["date_job"] = now.isoformat()

        # Limpiar enfermedad anterior si ya pasó tiempo
        if user.get("disease") and user.get("date_disease"):
            try:
                dd = datetime.datetime.fromisoformat(user["date_disease"])
                if (now - dd) > timedelta(days=3):
                    user.pop("disease", None)
                    user.pop("date_disease", None)
            except (ValueError, TypeError):
                pass

        await save_data(data_users, PATH_USERS)
        await interaction.response.send_message(
            f"✅ Trabajaste como **{trabajo_slug}** y ganaste **${pay}** y **{xp_gain} XP**.\n"
            f"Dinero actual: **${user['dinero']}** — Experiencia total: **{user['experiencia']}**.\n"
            f"🔸 Vuelve en ~24 horas para el siguiente /work.",
            ephemeral=False
        )

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Work(bot))