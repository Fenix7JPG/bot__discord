import discord
from discord.ext import commands
import asyncio
import os
import random
import tempfile
import yt_dlp
import datetime
from datetime import timezone, timedelta
from typing import Any
import json
import re
import aiohttp
import subprocess
import urllib.parse
import io
import cohere
from ia import IA
from pag import keep_alive
keep_alive()

waza
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

PATH_USERS = "data.json"
PATH_TRABAJOS = "trabajos.json"


file_lock = asyncio.Lock()

async def load_data(path: str) -> dict:
    """
    Carga y retorna el contenido JSON del archivo `path`.
    Si el archivo no existe, crea uno con la estructura por defecto {"xp": {}, "jobs": {}}.
    Esta función es asíncrona y usa file_lock para evitar condiciones de carrera.
    """
    async with file_lock:
        # Si no existe, inicializamos con estructura base
        if not os.path.exists(path):
            default = {"xp": {}, "jobs": {}}
            await save_data(default, path)
            return default

        def _read_sync():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        data = await asyncio.to_thread(_read_sync)

        return data

async def save_data(data: Any, path: str) -> None:
    """
    Guarda `data` como JSON en `path` de forma atómica.
    Usa un archivo temporal dentro del mismo directorio y luego lo reemplaza.
    Esta función es asíncrona y usa file_lock para evitar escrituras concurrentes.
    """
    async with file_lock:
        dirn = os.path.dirname(path) or "."
        os.makedirs(dirn, exist_ok=True)

        def _write_sync():
            # mkstemp crea un file descriptor seguro en el directorio especificado
            fd, tmp_path = tempfile.mkstemp(dir=dirn, prefix=".tmp-", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                # reemplazo atómico
                os.replace(tmp_path, path)
            finally:
                # cleanup si algo falló y tmp_path aún existe
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        await asyncio.to_thread(_write_sync)

    
@bot.event
async def on_ready():
    # Sincroniza los slash commands con Discord (puedes usar sync() por guild en desarrollo)
    await bot.tree.sync()
    print(f"Conectado como {bot.user} (id: {bot.user.id})")

@bot.tree.command(name="ping", description="Responde con Pong y la latencia")
async def ping(interaction: discord.Interaction):
    # Responder a la interacción
    await interaction.response.send_message(f"Pong! Latency: {bot.latency*1000:.0f} ms")

@bot.tree.command(name="jugar", description="registrarse en el juego")
async def jugar(interaction: discord.Interaction):
    # Responder a la interacción
    user_id = str(interaction.user.id)
    data_users = await load_data(PATH_USERS)
    if user_id not in data_users:
        data_users[user_id] = {
            "dinero": 0,
            "experiencia": 0,
            "date_job": None,
            "job": None,
            "salud": 100,
            "date_disease": None,
            "disease": None,
        }
        await save_data(data_users, PATH_USERS)
        await interaction.response.send_message("¡Te has registrado en el juego! Usa /trabajos")
    else:
        await interaction.response.send_message("Ya estás registrado en el juego.")
    

@bot.tree.command(name="trabajos", description="ver trabajos disponibles")
async def trabajos(interaction: discord.Interaction):
    JOBS_PAGE_SIZE = 8
    VIEW_TIMEOUT = 300 # segundos

    await interaction.response.defer()

    # --- leer archivo de trabajos (dentro de file_lock para seguridad) ---
    async with file_lock:
        def _read_sync():
            if not os.path.exists(PATH_TRABAJOS):
                return None
            with open(PATH_TRABAJOS, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    return None
        raw = await asyncio.to_thread(_read_sync)

    if not raw:
        await interaction.followup.send("No hay trabajos disponibles o el JSON está mal formado.", ephemeral=True)
        return

    # --- normalizar a lista de trabajos ---
    if isinstance(raw, dict):
        maybe = raw.get("jobs")
        if isinstance(maybe, list):
            jobs_list = maybe
        elif all(isinstance(v, dict) for v in raw.values()):
            jobs_list = list(raw.values())
        else:
            jobs_list = []
    elif isinstance(raw, list):
        jobs_list = raw
    else:
        jobs_list = []

    # asegurar cada item como dict con campos mínimos
    norm_jobs = []
    for j in jobs_list:
        if not isinstance(j, dict):
            continue
        norm = {
            "slug": j.get("slug") or (j.get("name","")).strip().lower().replace(" ", "-"),
            "name": j.get("name") or j.get("display_name") or "Sin nombre",
            "emoji": j.get("emoji",""),
            "level": j.get("level") or j.get("category",""),
            "required_experience": j.get("required_experience", j.get("required", 0))
        }
        norm_jobs.append(norm)

    if not norm_jobs:
        await interaction.followup.send("No hay trabajos válidos en el archivo.", ephemeral=True)
        return

    # --- View con paginación (botones) ---
    class JobsView(discord.ui.View):
        def __init__(self, jobs_list, author_id: int, page_size: int = JOBS_PAGE_SIZE, timeout: int = VIEW_TIMEOUT):
            super().__init__(timeout=timeout)
            self.jobs = jobs_list
            self.author_id = author_id
            self.page_size = page_size
            self.page = 0
            self.max_page = max(0, (len(self.jobs) - 1) // self.page_size)
            self.message = None
            self._update_buttons()

        def _update_buttons(self):
            try:
                self.prev_button.disabled = (self.page == 0)
                self.next_button.disabled = (self.page == self.max_page)
            except Exception:
                pass

        def build_embed(self):
            start = self.page * self.page_size
            end = start + self.page_size
            chunk = self.jobs[start:end]
            embed = discord.Embed(
                title="Trabajos disponibles",
                description=f"Página {self.page + 1}/{self.max_page + 1} — mostrando {len(chunk)} de {len(self.jobs)} trabajos",
                color=0x2F3136
            )
            for job in chunk:
                name = job.get("name", "Desconocido")
                emoji = job.get("emoji", "")
                level = job.get("level", "")
                req = job.get("required_experience", "N/A")
                title = f"{emoji} {name}" if emoji else name
                embed.add_field(name=title, value=f"Nivel: **{level}** — Req XP: **{req}**", inline=False)
            return embed

        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="jobs_prev")
        async def prev_button(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if interaction_btn.user.id != self.author_id:
                await interaction_btn.response.send_message("Solo quien abrió la lista puede usar estos botones.", ephemeral=True)
                return
            if self.page > 0:
                self.page -= 1
            self._update_buttons()
            await interaction_btn.response.edit_message(embed=self.build_embed(), view=self)

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="jobs_next")
        async def next_button(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if interaction_btn.user.id != self.author_id:
                await interaction_btn.response.send_message("Solo quien abrió la lista puede usar estos botones.", ephemeral=True)
                return
            if self.page < self.max_page:
                self.page += 1
            self._update_buttons()
            await interaction_btn.response.edit_message(embed=self.build_embed(), view=self)

        @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="jobs_close")
        async def close_button(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if interaction_btn.user.id != self.author_id:
                await interaction_btn.response.send_message("Solo quien abrió la lista puede usar estos botones.", ephemeral=True)
                return
            for child in self.children:
                child.disabled = True
            await interaction_btn.response.edit_message(content="Vista cerrada.", embed=None, view=self)
            self.stop()

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            try:
                if getattr(self, "message", None):
                    await self.message.edit(view=self)
            except Exception:
                pass

    view = JobsView(norm_jobs, interaction.user.id, page_size=JOBS_PAGE_SIZE, timeout=VIEW_TIMEOUT)
    embed = view.build_embed()
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message


@bot.tree.command(name="postularse_trabajo", description="Postúlate a un trabajo (usa el slug o el nombre)")
async def postularse_trabajo(interaction: discord.Interaction, trabajo: str):
    # Cargar datos
    data_users = await load_data(PATH_USERS)
    data_jobs = await load_data(PATH_TRABAJOS)
    user_id = str(interaction.user.id)

    # Verificar perfil
    if user_id not in data_users:
        await interaction.response.send_message("❌ No tienes perfil creado. Usa el comando para crear tu perfil primero.", ephemeral=True)
        return

    jobs_list = data_jobs.get("jobs", [])
    # Buscar por slug o por nombre (case-insensitive)
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



    # Si ya tiene ese trabajo, avisar (opcional)
    if data_users[user_id].get("job") == job.get("slug"):
        await interaction.response.send_message(f"ℹ️ {interaction.user.mention}, ya trabajas como **{job.get('name')}**.", ephemeral=True)
        return

    # Probabilidad basada en experiencia
    required_exp = int(job.get("required_experience", 0))
    user_exp = int(data_users[user_id].get("exp", 0))

    # Método simple de randomización
    if random.randint(0, required_exp) <= user_exp:
        data_users[user_id]["job"] = trabajo
        await save_data(data_users,PATH_USERS)
        await interaction.response.send_message(f"✅ ¡Felicidades {interaction.user.mention}! Ahora trabajas como **{trabajo}**.")
    else:
        await interaction.response.send_message(f"❌ Lo siento {interaction.user.mention}, no fuiste aceptado para **{trabajo}**.")

@bot.tree.command(name="stats", description="Muestra tus estadísticas: dinero, trabajo, experiencia y salud (solo tuyo)")
async def stats(interaction: discord.Interaction):
    # Cargar solo los datos de usuarios
    data_users = await load_data(PATH_USERS)
    user_id = str(interaction.user.id)

    # Verificar si existe el perfil
    if user_id not in data_users:
        await interaction.response.send_message(
            "❌ No tienes perfil creado. Usa el comando para crear tu perfil primero.",
            ephemeral=True
        )
        return

    user = data_users[user_id]

    # Normalizar claves (soporta distintas estructuras)
    try:
        dinero = int(user.get("dinero", user.get("money", 0)))
    except Exception:
        dinero = 0

    trabajo_slug = user.get("trabajo") or user.get("job")  # puede ser None

    try:
        experiencia = int(user.get("experiencia", user.get("exp", 0)))
    except Exception:
        experiencia = 0

    # Salud (soporta 'salud' o 'health')
    salud_raw = user.get("salud", user.get("health", 100))
    try:
        salud = int(salud_raw)
    except Exception:
        salud = 100

    enfermedad = user.get("disease")  # nombre de la enfermedad si existe
    date_disease = user.get("date_disease")

    # Preparar texto del trabajo (sin consultar jobs.json)
    if trabajo_slug:
        trabajo_display = f"`{trabajo_slug}`"
    else:
        trabajo_display = "Sin trabajo"

    # Crear embed simple
    embed = discord.Embed(
        title=f"📊 Estadísticas — {interaction.user.display_name}",
        colour=discord.Colour.blurple()
    )
    embed.add_field(name="💰 Dinero", value=f"${dinero:,}", inline=True)
    embed.add_field(name="🧾 Experiencia", value=f"{experiencia}", inline=True)
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

@bot.tree.command(name="work", description="Trabaja para ganar dinero y experiencia (requiere tener un trabajo)")
async def work(interaction: discord.Interaction):
    """
    leer  el data.json que tiene una estructura como esta
        {
    "1385034045494268064": {
        "dinero": 12345778,
        "experiencia": 0,
        "date_job": null,
        "job": null,
        "salud": 100,
        "date_disease": null,
        "disease": null
    },
    y dependiente de  date_job ,
    si date_job que es la fecha de cuando se hizo el trabajo, (se hizo /work)
    si aun no a pasado 24 horas desde esa fecha, hay probalidades de contraer una enfermedad
    y si no, se puede hacer el trabajo y ganar dinero y experiencia
    y guardar eso en el data.json

    """
    pass

    user_id = str(interaction.user.id)
    # Cargar usuarios
    data_users = await load_data(PATH_USERS)

    if user_id not in data_users:
        await interaction.response.send_message("❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True)
        return

    user = data_users[user_id]

    # Normalizar claves
    trabajo_slug = user.get("trabajo") or user.get("job")
    if not trabajo_slug:
        await interaction.response.send_message("❌ No tienes un trabajo asignado. Usa /postularse_trabajo para conseguir uno.", ephemeral=True)
        return

    # Cargar trabajos (intenta leer PATH_TRABAJOS - puede ser dict o lista)
    data_jobs = await load_data(PATH_TRABAJOS)
    raw_jobs = data_jobs.get("jobs") if isinstance(data_jobs, dict) else data_jobs
    jobs_list = raw_jobs or []

    # Buscar trabajo por slug o nombre
    job = None
    if isinstance(jobs_list, dict):
        # si jobs.json tiene forma {"slug": {...}}
        job = jobs_list.get(trabajo_slug)
    if not job and isinstance(jobs_list, list):
        job = next((j for j in jobs_list if (j.get("slug") == trabajo_slug or j.get("name", "").lower() == str(trabajo_slug).lower())), None)

    # Si no hay información del job, seguiremos con valores por defecto
    required_exp = 0
    base_pay = None
    if job:
        try:
            required_exp = int(job.get("required_experience", job.get("required", 0) or 0))
        except Exception:
            required_exp = 0
        # Intentar distintas claves para salario
        for key in ("salary", "pay", "income", "wage", "salary_per_day", "pago","sueldo"):
            if job.get(key) is not None:
                try:
                    base_pay = int(job.get(key))
                    break
                except Exception:
                    pass

    # Si no hay salario definido, crear uno basado en required_exp y random
    if base_pay is None:
        base_pay = 50 + (required_exp * 10) + random.randint(0, 100)

    # experiencia a ganar base
    xp_gain = random.randint(5, 20) + (required_exp // 2)

    # Leer última fecha de trabajo
    now = datetime.datetime.now(tz=timezone.utc)
    last_work_iso = user.get("date_job")
    last_work_dt = None
    if last_work_iso:
        try:
            # soportar ISO y strings sin tz
            last_work_dt = datetime.datetime.fromisoformat(last_work_iso)
            if last_work_dt.tzinfo is None:
                last_work_dt = last_work_dt.replace(tzinfo=timezone.utc)
        except Exception:
            last_work_dt = None

    allow_normal = True
    hours_since = None
    if last_work_dt:
        delta = now - last_work_dt
        hours_since = delta.total_seconds() / 3600.0
        if hours_since < 24:
            allow_normal = False

    # Si aún no han pasado 24h -> riesgo de enfermedad o pago reducido
    if not allow_normal:
        # Probabilidad de enfermarse: mayor si intentas muy seguido.
        # Ejemplo: si han pasado 0 horas -> 45% ; si han pasado 12h -> 20% ; si 23h -> 5%
        hazard = max(5, min(45, int((24 - hours_since) * (45 / 24))))
        roll = random.randint(1, 100)
        if roll <= hazard:
            # Enfermarse: aplica efecto negativo
            diseases = [
                {"name": "resfriado", "damage": random.randint(5, 12)},
                {"name": "gripe", "damage": random.randint(8, 20)},
                {"name": "intoxicación alimentaria", "damage": random.randint(6, 18)},
                {"name": "fiebre", "damage": random.randint(7, 15)},
                {"name": "fatiga severa", "damage": random.randint(5, 14)}
            ]
            chosen = random.choice(diseases)
            # Reducir salud
            current_health = int(user.get("salud", 100))
            new_health = max(0, current_health - chosen["damage"])
            user["salud"] = new_health
            user["disease"] = chosen["name"]
            user["date_disease"] = now.isoformat()
            # No gana dinero (o podrías hacer que pierda algo)
            # Opcional: perder una pequeña cantidad de dinero por atención médica
            dinero_actual = int(user.get("dinero", user.get("money", 0) or 0))
            gasto_med = min(dinero_actual, random.randint(0, max(0, int(dinero_actual * 0.1))))
            user["dinero"] = dinero_actual - gasto_med

            # actualizar date_job para bloquear intentos inmediatos (se registra que intentó trabajar)
            user["date_job"] = now.isoformat()
            # guardar experiencia menor por intento fallido
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
            # No se enfermó, pero paga reducida por sobreesfuerzo
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

    # Si llegamos aquí: han pasado >=24h o no hay fecha anterior -> trabajo normal
    # Calcular variación aleatoria del pago
    variability = random.uniform(0.9, 1.3)
    pay = max(1, int(base_pay * variability))
    user["dinero"] = int(user.get("dinero", user.get("money", 0) or 0)) + pay
    user["experiencia"] = int(user.get("experiencia", user.get("exp", 0) or 0)) + xp_gain
    user["date_job"] = now.isoformat()
    # limpiar enfermedad anterior si ya pasó tiempo
    if user.get("disease") and user.get("date_disease"):
        try:
            dd = datetime.datetime.fromisoformat(user["date_disease"])
            if (now - dd) > timedelta(days=3):
                user.pop("disease", None)
                user.pop("date_disease", None)
        except Exception:
            pass

    await save_data(data_users, PATH_USERS)

    await interaction.response.send_message(
        f"✅ Trabajaste como **{trabajo_slug}** y ganaste **${pay}** y **{xp_gain} XP**.\n"
        f"Dinero actual: **${user['dinero']}** — Experiencia total: **{user['experiencia']}**.\n"
        f"🔸 Vuelve en ~24 horas para el siguiente /work.",
        ephemeral=False
    )


@bot.tree.command(name="curarse", description="Curarte gastando dinero. Si curas más vida, cuesta más.")
async def curarse(interaction: discord.Interaction,cantidad:int):
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

    # Cantidad deseada a curar (si no se especifica, curar al máximo)
    faltante = 100 - salud_actual
    if cantidad is None:
        heal_amount = faltante
    else:
        if cantidad <= 0:
            await interaction.response.send_message("🔸 La cantidad debe ser mayor que 0.", ephemeral=True)
            return
        heal_amount = min(cantidad, faltante)

    # Fórmula de costo:
    # costo base por HP + pequeño término cuadrático para que curar mucho cueste más por unidad.
    base_cost_per_hp = 5            # puedes ajustar esto
    scaling_quadratic = 0.20        # factor que aplica al (heal_amount ** 2)
    cost = int(heal_amount * base_cost_per_hp + (heal_amount ** 2) * scaling_quadratic)
    cost = max(1, cost)

    if dinero_actual < cost:
        await interaction.response.send_message(
            f"❌ No tienes suficiente dinero. Necesitas **${cost}**, tienes **${dinero_actual}**.",
            ephemeral=True
        )
        return

    # Aplicar curación y gasto
    user["salud"] = min(100, salud_actual + heal_amount)
    user["dinero"] = dinero_actual - cost

    # Si tenía una enfermedad y ahora tiene buena salud, limpiar la enfermedad
    try:
        if user.get("disease") and user.get("date_disease"):
            # criterio: si salud >= 80, consideramos que se recuperó de la enfermedad
            if user["salud"] >= 80:
                user.pop("disease", None)
                user.pop("date_disease", None)
    except Exception:
        pass

    await save_data(data_users, PATH_USERS)

    await interaction.response.send_message(
        f"💊 {interaction.user.mention}, te curaste **{heal_amount}** de vida por **${cost}**.\n"
        f"🩺 Salud: **{salud_actual} → {user['salud']}** — Dinero restante: **${user['dinero']}**.",
        ephemeral=False
    )

import math
from typing import List, Tuple

# --- helpers para blackjack ---
def create_deck() -> List[str]:
    suits = ["♠", "♥", "♦", "♣"]
    ranks = ["A"] + [str(n) for n in range(2, 11)] + ["J", "Q", "K"]
    return [f"{r}{s}" for s in suits for r in ranks]

def card_value(card: str) -> int:
    rank = card[:-1]  # "10♠" -> "10"
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11  # inicialmente contó como 11; ajuste lo maneja hand_value
    return int(rank)

def hand_value(cards: List[str]) -> Tuple[int, bool]:
    """Devuelve (mejor_valor, is_soft) donde is_soft indica si hay As con valor 11."""
    total = 0
    aces = 0
    for c in cards:
        r = c[:-1]
        if r == "A":
            aces += 1
            total += 11
        elif r in ("J", "Q", "K"):
            total += 10
        else:
            total += int(r)
    # Ajustar ases
    while total > 21 and aces:
        total -= 10
        aces -= 1
    is_soft = any((c[:-1] == "A") for c in cards) and total <= 21
    return total, is_soft

def card_display(card: str) -> str:
    return card

# --- comando /blackjack ---
@bot.tree.command(name="blackjack", description="Juega una mano de blackjack. Usa una apuesta (entera).")
async def blackjack(interaction: discord.Interaction, apuesta: int):
    if apuesta <= 0:
        await interaction.response.send_message("🔸 La apuesta debe ser un número entero mayor que 0.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    data_users = await load_data(PATH_USERS)

    if user_id not in data_users:
        await interaction.response.send_message("❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True)
        return

    current_money = int(data_users[user_id].get("dinero", data_users[user_id].get("money", 0) or 0))
    if current_money < apuesta:
        await interaction.response.send_message("❌ No tienes suficiente dinero para esa apuesta.", ephemeral=True)
        return

    deck = create_deck()
    random.shuffle(deck)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    base_bet = int(apuesta)
    current_bet = base_bet

    # Deduct initial bet
    data_users[user_id]['dinero'] = current_money - base_bet
    await save_data(data_users, PATH_USERS)

    class BlackjackView(discord.ui.View):
        def __init__(self, *, author_id: int, timeout: int = 120):
            super().__init__(timeout=timeout)
            self.author_id = author_id
            self.deck = deck
            self.player = player
            self.dealer = dealer
            self.base_bet = base_bet
            self.current_bet = current_bet
            self.ended = False
            self.message = None
            self.first_action = True

        def build_embed(self, reveal_dealer=False, note: str = ""):
            if reveal_dealer:
                dealer_display = " ".join(card_display(c) for c in self.dealer)
                dealer_val, _ = hand_value(self.dealer)
                dealer_line = f"{dealer_display} — **{dealer_val}**"
            else:
                dealer_display = f"{card_display(self.dealer[0])} 🂠"
                dealer_val, _ = hand_value([self.dealer[0]])
                dealer_line = f"{dealer_display} — visible: **{dealer_val}**"

            player_display = " ".join(card_display(c) for c in self.player)
            player_val, _ = hand_value(self.player)

            embed = discord.Embed(
                title=f"🃏 Blackjack — Apuesta ${self.base_bet}",
                description=note or "Elige una acción: Hit / Stand / Double Down / Surrender",
                color=0x2F3136
            )
            embed.add_field(name="Dealer", value=dealer_line, inline=False)
            embed.add_field(name=f"{interaction.user.display_name} — Mano", value=f"{player_display} — **{player_val}**", inline=False)
            embed.set_footer(text=f"Apuesta actual: ${self.current_bet} — Tu saldo: ${data_users[user_id].get('dinero',0)}")
            return embed

        # CORRECCIÓN: primero interaction, luego button
        @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="bj_hit")
        async def hit(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if interaction_btn.user.id != self.author_id:
                await interaction_btn.response.send_message("Solo quien inició la mano puede usar los botones.", ephemeral=True)
                return
            if self.ended:
                await interaction_btn.response.send_message("La mano ya terminó.", ephemeral=True)
                return

            self.first_action = False
            self.player.append(self.deck.pop())
            pv, _ = hand_value(self.player)

            if pv > 21:
                self.ended = True
                note = f"💥 Te pasaste con {pv}. Pierdes ${self.current_bet}."
                embed = self.build_embed(reveal_dealer=True, note=note)
                for child in self.children:
                    child.disabled = True
                await interaction_btn.response.edit_message(embed=embed, view=self)
                self.stop()
                return
            else:
                embed = self.build_embed(note=f"Has pedido carta. Tu total: {pv}.")
                self._disable_double_surrender(False)
                await interaction_btn.response.edit_message(embed=embed, view=self)

        @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="bj_stand")
        async def stand(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if interaction_btn.user.id != self.author_id:
                await interaction_btn.response.send_message("Solo quien inició la mano puede usar los botones.", ephemeral=True)
                return
            if self.ended:
                await interaction_btn.response.send_message("La mano ya terminó.", ephemeral=True)
                return

            self.first_action = False
            await self.resolve(interaction_btn, reveal_note="Te plantaste. Jugando el dealer...")

        @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, custom_id="bj_double")
        async def double(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if interaction_btn.user.id != self.author_id:
                await interaction_btn.response.send_message("Solo quien inició la mano puede usar los botones.", ephemeral=True)
                return
            if self.ended:
                await interaction_btn.response.send_message("La mano ya terminó.", ephemeral=True)
                return
            if not self.first_action:
                await interaction_btn.response.send_message("Double Down sólo está permitido como primera acción.", ephemeral=True)
                return

            latest = await load_data(PATH_USERS)
            user_money = int(latest[user_id].get("dinero", latest[user_id].get("money", 0) or 0))
            if user_money < self.base_bet:
                await interaction_btn.response.send_message("No tienes suficiente dinero para doblar la apuesta.", ephemeral=True)
                return

            latest[user_id]['dinero'] = user_money - self.base_bet
            await save_data(latest, PATH_USERS)
            data_users[user_id]['dinero'] = latest[user_id]['dinero']

            self.current_bet += self.base_bet
            self.player.append(self.deck.pop())
            pv, _ = hand_value(self.player)
            if pv > 21:
                self.ended = True
                note = f"💥 Dobles y te pasaste con {pv}. Pierdes ${self.current_bet}."
                embed = self.build_embed(reveal_dealer=True, note=note)
                for child in self.children:
                    child.disabled = True
                await interaction_btn.response.edit_message(embed=embed, view=self)
                self.stop()
                return
            else:
                await self.resolve(interaction_btn, reveal_note=f"Doblaste a ${self.current_bet}. Tu total: {pv}. Dealer jugando...")

        @discord.ui.button(label="Surrender", style=discord.ButtonStyle.danger, custom_id="bj_surrender")
        async def surrender(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if interaction_btn.user.id != self.author_id:
                await interaction_btn.response.send_message("Solo quien inició la mano puede usar los botones.", ephemeral=True)
                return
            if self.ended:
                await interaction_btn.response.send_message("La mano ya terminó.", ephemeral=True)
                return
            if not self.first_action:
                await interaction_btn.response.send_message("Surrender sólo está permitido como primera acción.", ephemeral=True)
                return

            refund = self.base_bet // 2
            latest = await load_data(PATH_USERS)
            latest[user_id]['dinero'] = int(latest[user_id].get('dinero', 0)) + refund
            await save_data(latest, PATH_USERS)
            data_users[user_id]['dinero'] = latest[user_id]['dinero']

            self.ended = True
            note = f"➗ Te rendiste. Recuperas la mitad: ${refund}."
            embed = self.build_embed(reveal_dealer=True, note=note)
            for child in self.children:
                child.disabled = True
            await interaction_btn.response.edit_message(embed=embed, view=self)
            self.stop()
            return

        async def resolve(self, interaction_btn: discord.Interaction, reveal_note: str = ""):
            dv, dsoft = hand_value(self.dealer)
            while True:
                dv, dsoft = hand_value(self.dealer)
                if dv < 17:
                    self.dealer.append(self.deck.pop())
                    continue
                break

            pv, _ = hand_value(self.player)
            dv, _ = hand_value(self.dealer)

            note = reveal_note + "\n\n"
            latest = await load_data(PATH_USERS)
            latest[user_id].setdefault('dinero', 0)

            player_blackjack = (len(self.player) == 2 and pv == 21)
            dealer_blackjack = (len(self.dealer) == 2 and dv == 21)

            if player_blackjack and not dealer_blackjack:
                payout = int(self.base_bet * 2.5)
                latest[user_id]['dinero'] = int(latest[user_id]['dinero']) + payout
                note += f"🎉 ¡Blackjack! Ganas ${int(self.base_bet * 1.5)} (pago 3:2)."
            elif player_blackjack and dealer_blackjack:
                latest[user_id]['dinero'] = int(latest[user_id]['dinero']) + self.base_bet
                note += "🤝 Ambos tienen Blackjack — Empate (push). Recuperas tu apuesta."
            elif pv > 21:
                note += f"💥 Te pasaste con {pv}. Pierdes ${self.current_bet}."
            elif dv > 21:
                latest[user_id]['dinero'] = int(latest[user_id]['dinero']) + (self.current_bet * 2)
                note += f"🏆 Dealer se pasó ({dv}). Ganas ${self.current_bet}."
            else:
                if pv > dv:
                    latest[user_id]['dinero'] = int(latest[user_id]['dinero']) + (self.current_bet * 2)
                    note += f"🏆 Ganaste {pv} vs {dv}. Ganas ${self.current_bet}."
                elif pv == dv:
                    latest[user_id]['dinero'] = int(latest[user_id]['dinero']) + self.current_bet
                    note += f"🤝 Empate {pv} vs {dv} — push. Recuperas tu apuesta."
                else:
                    note += f"❌ Perdiste {pv} vs {dv}. Pierdes ${self.current_bet}."

            await save_data(latest, PATH_USERS)
            data_users[user_id]['dinero'] = latest[user_id]['dinero']

            self.ended = True
            embed = self.build_embed(reveal_dealer=True, note=note)
            for child in self.children:
                child.disabled = True
            await interaction_btn.response.edit_message(embed=embed, view=self)
            self.stop()

        def _disable_double_surrender(self, allow: bool):
            for child in self.children:
                if getattr(child, "custom_id", "") in ("bj_double", "bj_surrender"):
                    child.disabled = not allow

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            try:
                if getattr(self, "message", None):
                    embed = self.build_embed(note="⏲️ Tiempo agotado. La mano se canceló.")
                    await self.message.edit(embed=embed, view=self)
            except Exception:
                pass
            self.stop()

    view = BlackjackView(author_id=interaction.user.id, timeout=180)
    embed = view.build_embed(note="Repartiendo cartas...")
    await interaction.response.send_message(embed=embed, view=view)
    sent = await interaction.original_response()
    view.message = sent


@bot.tree.command(name="ruleta", description="Apuesta a rojo, negro o 0. Uso: /ruleta opcion apuesta (ej: /ruleta rojo 100)")
async def ruleta(interaction: discord.Interaction, opcion: str, apuesta: int):
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



@bot.tree.command(name="d6", description="Lanza un dado de 6 caras 🎲")
async def d6(interaction: discord.Interaction):
    result = random.randint(1, 6)
    await interaction.response.send_message(f"🎲 Has lanzado un **d6** → **{result}**")

@bot.tree.command(name="d10", description="Lanza un dado de 10 caras 🎲")
async def d10(interaction: discord.Interaction):
    result = random.randint(1, 10)
    await interaction.response.send_message(f"🎲 Has lanzado un **d10** → **{result}**")

@bot.tree.command(name="d20", description="Lanza un dado de 20 caras 🎲")
async def d20(interaction: discord.Interaction):
    result = random.randint(1, 20)
    await interaction.response.send_message(f"🎲 Has lanzado un **d20** → **{result}**")

# Sesión http reutilizable
session: aiohttp.ClientSession | None = None

@bot.tree.command(name="cat", description="Envía una imagen de gato al azar 🐱")
async def cat(interaction: discord.Interaction):
    await interaction.response.defer()  # evita timeouts mientras buscamos la imagen
    global session
    if session is None:
        session = aiohttp.ClientSession()

    # Intentamos primero TheCatAPI, luego fallback a aws.random.cat o cataas
    urls_to_try = [
        ("https://api.thecatapi.com/v1/images/search", "json", lambda j: j[0]["url"]),
        ("https://aws.random.cat/meow", "json", lambda j: j["file"]),
        ("https://cataas.com/cat?json=true", "json", lambda j: "https://cataas.com" + j["url"]),
    ]

    image_url = None
    for url, rtype, extractor in urls_to_try:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    if rtype == "json":
                        j = await resp.json()
                        image_url = extractor(j)
                        if image_url:
                            break
                    else:
                        text = await resp.text()
                        if text:
                            image_url = text
                            break
        except Exception:
            # si falla, continuamos al siguiente servicio
            continue

    if not image_url:
        await interaction.followup.send("❌ No pude obtener una imagen de gato ahora. Intenta de nuevo más tarde.")
        return

    embed = discord.Embed(title="", color=0xF5A9B8)
    embed.set_image(url=image_url)
    embed.set_footer(text="Imagen de gato 🐱")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="raidear", description="Raider el server")
async def raidear(interaction: discord.Interaction):
    await interaction.response.send_message("...", ephemeral=True)


# RULETA RUSA

# Añade esto a tu bot (asumiendo que ya tienes `bot` definido y funcionando
# con @bot.tree.command como en tu ejemplo `d20`).
import discord
from discord import app_commands
import random
import asyncio

# Guarda juegos por canal para permitir múltiples juegos simultáneos en distintos canales
games_by_channel: dict[int, "RussianRouletteGame"] = {}

class RussianRouletteView(discord.ui.View):
    def __init__(self, game: "RussianRouletteGame"):
        super().__init__(timeout=None)
        self.game = game

    @discord.ui.button(label="Unirse", style=discord.ButtonStyle.success, custom_id="rr_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        added = await self.game.add_player(interaction.user)
        if added:
            # Edita el mensaje de la vista para mostrar jugadores actuales
            await interaction.response.edit_message(content=self.game.join_message_text(), view=self)
        else:
            await interaction.response.send_message("Ya estás en la lista o el juego ya empezó.", ephemeral=True)

    @discord.ui.button(label="Abandonar", style=discord.ButtonStyle.danger, custom_id="rr_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        removed = await self.game.remove_player(interaction.user)
        if removed:
            await interaction.response.edit_message(content=self.game.join_message_text(), view=self)
        else:
            await interaction.response.send_message("No estabas en la lista o el juego ya empezó.", ephemeral=True)

    @discord.ui.button(label="Empezar", style=discord.ButtonStyle.primary, custom_id="rr_start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.started:
            await interaction.response.send_message("El juego ya empezó.", ephemeral=True)
            return
        if len(self.game.players) < 2:
            await interaction.response.send_message("Se necesitan al menos 2 jugadores para empezar.", ephemeral=True)
            return

        # Deshabilita botones para evitar cambios durante la partida
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=self.game.join_message_text(starting=True), view=self)

        # Lanzar la partida en background
        asyncio.create_task(self.game.run_game())

class RussianRouletteGame:
    def __init__(self, channel: discord.TextChannel, initiator: discord.Member):
        self.channel = channel
        self.players: list[discord.Member] = []
        self.started = False
        # tambor: lista de 6, True = bala
        self.chambers = [False]*6
        self.current_chamber_index = 0  # índice en el tambor (0..5)
        self.current_player_idx = 0     # índice en self.players
        self.reset_event = asyncio.Event()  # para resetear countdown
        self.countdown_active = False
        self.initiator = initiator
        self.view_message: discord.Message | None = None

    def join_message_text(self, starting: bool = False) -> str:
        lines = ["**— RULETA RUSA —**",
                 "Pulsa **Unirse** para entrar o **Abandonar** para salir."]
        if not self.players:
            lines.append("\n**Jugadores (0):** (aún nadie)")
        else:
            names = ", ".join(p.display_name for p in self.players)
            lines.append(f"\n**Jugadores ({len(self.players)}):** {names}")
        if starting:
            lines.append("\n> El juego ha comenzado. ¡Suerte!")
        return "\n".join(lines)

    async def add_player(self, user: discord.User) -> bool:
        if self.started:
            return False
        if any(p.id == user.id for p in self.players):
            return False
        # intentar obtener Member si es posible
        member = user if isinstance(user, discord.Member) else await self.channel.guild.fetch_member(user.id)
        self.players.append(member)
        return True

    async def remove_player(self, user: discord.User) -> bool:
        if self.started:
            return False
        for p in self.players:
            if p.id == user.id:
                self.players.remove(p)
                return True
        return False

    def _place_bullet(self):
        self.chambers = [False]*6
        idx = random.randrange(6)
        self.chambers[idx] = True
        self.current_chamber_index = 0  # empezamos por la cámara 0 de la lista
        # Nota: la "posición" relativa se recorre en cada disparo

    async def run_game(self):
        # marca inicio
        self.started = True
        # si por alguna razón ya no hay suficientes jugadores, termina
        if len(self.players) < 2:
            await self.channel.send("No hay suficientes jugadores. Juego cancelado.")
            self.cleanup()
            return

        # orden de juego: ya por orden de ingreso
        await self.channel.send("Orden de juego:\n" + "\n".join(f"{i+1}. {p.mention}" for i, p in enumerate(self.players)))

        # preparar tambor
        self._place_bullet()

        # ciclo principal: hasta que quede 1 jugador o se cancele
        while len(self.players) > 1:
            current_player = self.players[self.current_player_idx % len(self.players)]
            # Anunciar turno y esperar 5s con posibilidad de reset por mensajes
            warn_msg = await self.channel.send(f"🔫 **Turno de {current_player.mention}** — se prepara para disparar... (5s)")
            # Esperar el countdown con resets
            await self._wait_with_resets()

            # Resolver disparo: revisar la cámara actual
            chamber_has_bullet = self.chambers[self.current_chamber_index]
            if chamber_has_bullet:
                # Muere
                await self.channel.send(f"💥 **{current_player.mention}** se ha disparado. Ha muerto.")
                # remover jugador
                self.players = [p for p in self.players if p.id != current_player.id]
                # si queda 1 solo -> anunciar ganador y terminar
                if len(self.players) <= 1:
                    if self.players:
                        await self.channel.send(f"🏆 **{self.players[0].mention}** es el último en pie. ¡Ganador!")
                    else:
                        await self.channel.send("No quedan jugadores. Fin del juego.")
                    self.cleanup()
                    return
                # recargar arma (colocar bala aleatoriamente) y seguir; current_player eliminado
                self._place_bullet()
                # current_player_idx apunta al siguiente jugador automáticamente (mantenemos el mismo índice
                # porque la lista se acortó; no incrementamos)
                if self.current_player_idx >= len(self.players):
                    self.current_player_idx = 0
                await self.channel.send("🔄 Se recarga el arma y la partida continúa.")
            else:
                # Click — vivo
                await self.channel.send(f"🔒 **{current_player.mention}** ha disparado y *vive* (click).")
                # avanzar la cámara y el jugador
                self.current_chamber_index = (self.current_chamber_index + 1) % 6
                self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

        # Si sale del while y queda uno
        if len(self.players) == 1:
            await self.channel.send(f"🏆 **{self.players[0].mention}** es el último en pie. ¡Ganador!")
        else:
            await self.channel.send("Juego terminado.")
        self.cleanup()

    async def _wait_with_resets(self):
        # Limpia y usa self.reset_event para reiniciar si se recibe señal de actividad
        # la lógica: si reset_event se activa durante los 5s, se reinicia la espera a 5s.
        while True:
            self.reset_event.clear()
            try:
                await asyncio.wait_for(self.reset_event.wait(), timeout=5.0)
                # si aquí llegamos, alguien reseteó -> repetir bucle y volver a esperar 5s
                continue
            except asyncio.TimeoutError:
                # no hubo resets en 5s -> continuar
                break

    def reset_countdown(self):
        # llamado desde on_message cuando haya actividad en el canal
        # set el event para reiniciar la espera actual
        try:
            self.reset_event.set()
        except Exception:
            pass

    def cleanup(self):
        # Quitar referencia al juego en global
        try:
            del games_by_channel[self.channel.id]
        except KeyError:
            pass

# Comando para lanzar la interfaz de unión / inicio de la ruleta
@bot.tree.command(name="ruleta-rusa", description="Inicia una partida de ruleta rusa (juego, no violencia real).")
async def ruleta_rusa(interaction: discord.Interaction):
    channel = interaction.channel
    if channel is None or not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Este comando solo puede usarse en un canal de texto del servidor.", ephemeral=True)
        return

    # Si ya hay un juego en este canal, no crear otro
    if channel.id in games_by_channel:
        await interaction.response.send_message("Ya hay una ruleta activa en este canal.", ephemeral=True)
        return

    # Crear juego y vista
    game = RussianRouletteGame(channel=channel, initiator=interaction.user)
    view = RussianRouletteView(game)
    content = game.join_message_text()
    msg = await channel.send(content, view=view)
    game.view_message = msg
    games_by_channel[channel.id] = game
    await interaction.response.send_message("Se ha creado la ruleta. ¡Únete con los botones en el mensaje!", ephemeral=True)




IA = IA(COHERE_API_KEY)

# Evento que escucha mensajes para reiniciar la cuenta regresiva si hay actividad
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    if not isinstance(message.content, str) or not message.content:
        return

    game = games_by_channel.get(getattr(message.channel, "id", None))
    if game and game.started:
        # Reiniciar countdown del juego en este canal
        game.reset_countdown()
    
    if bot.user in message.mentions:
        # Responder usando IA
        try:
            reply = IA.chat(f"{message.content}")
        except Exception as e:
            reply = f"Locutor: Se le fundio la cabeza, no puede responder. Intenta llamar a Fenix, ERROR {e}"
        await message.reply(f"{reply}")
    else:
        IA.guardar_mensj(f"{message.content}")
        if random.randint(0,100) == 0:
            reply = IA.actu()
            if reply:
                await message.reply(f"{reply}")

    
    try:
        await bot.process_commands(message)
    except Exception:
        # Si tu bot es discord.Client con app_commands y no usas process_commands, omite esto
        pass



bot.run(DISCORD_TOKEN)


















