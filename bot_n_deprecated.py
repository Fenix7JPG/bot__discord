import discord
from ytmp3 import ytmp3
from discord.ext import commands
import asyncio
import os
from typing import Optional
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
    #await bot.change_presence(status=discord.Status.invisible) #poner estado invisible



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
####################################################################################
ytmp3(bot.tree)
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


DEFAULT_TIMEOUT = 10  # segundos por defecto si no hay FFMPEG_CHECK_TIMEOUT en env

# Comando simple (no cog)
@bot.tree.command(name="checkffmpeg", description="Revisa checkffmpeg")
async def checkffmpeg(interaction: discord.Interaction):
    """
    Uso: /checkffmpeg
    Responde inmediatamente y luego actualiza con resultado detallado.
    """
    timeout = int(os.getenv("FFMPEG_CHECK_TIMEOUT", DEFAULT_TIMEOUT))

    # RESPUESTA INMEDIATA a la interaction (evita "Application did not respond")
    try:
        await interaction.response.send_message("🔎 Comprobando `ffmpeg`... (esto puede tardar unos segundos)")
        status_msg = await interaction.original_response()  # Message objeto a editar después
    except Exception as e:
        # En caso raro de fallo al enviar la respuesta inicial, enviamos un followup (mala señal)
        # pero normalmente NO deberías llegar aquí si interaction.response.send_message tuvo éxito.
        print("Error enviando la respuesta inicial:", e)
        await interaction.followup.send("🔎 Comprobando `ffmpeg`... (no se pudo enviar mensaje inicial correctamente)")
        return

    # 1) Comprobación rápida con shutil.which
    ff_path = shutil.which("ffmpeg")
    if not ff_path:
        reply_text = ("❌ `ffmpeg` no se encontró en PATH (`shutil.which` devolvió None).\n"
                      "Intentaré ejecutar `ffmpeg -version` de todos modos para ver si hay más información.")
        try:
            await status_msg.edit(content=reply_text)
        except Exception:
            await interaction.followup.send(reply_text)

    # 2) Intento de ejecutar ffmpeg -version (async) con timeout
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        msg = ("❌ `FileNotFoundError`: `ffmpeg` no está instalado o no está en PATH.\n"
               "Comprueba la shell del servicio: `which ffmpeg` o `ffmpeg -version`.")
        print("FileNotFoundError al crear_subprocess_exec para ffmpeg")
        try:
            await status_msg.edit(content=msg)
        except Exception:
            await interaction.followup.send(msg)
        return
    except Exception as e:
        tb = traceback.format_exc()
        print("Excepción al crear subproceso ffmpeg:\n", tb)
        try:
            await status_msg.edit(content=f"❌ Error al intentar ejecutar `ffmpeg`: ```{str(e)[:1500]}```")
        except Exception:
            await interaction.followup.send(f"❌ Error al intentar ejecutar `ffmpeg`: ```{str(e)[:1500]}```")
        return

    # Esperar la salida con timeout
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await status_msg.edit(content=f"⏱️ Tiempo de espera excedido después de {timeout}s. El proceso fue terminado.")
        print(f"ffmpeg check: timeout after {timeout}s")
        return
    except Exception as e:
        tb = traceback.format_exc()
        print("Error al esperar la comunicación del proceso ffmpeg:\n", tb)
        try:
            await status_msg.edit(content=f"❌ Error al ejecutar `ffmpeg`: ```{str(e)[:1500]}```")
        except Exception:
            await interaction.followup.send(f"❌ Error al ejecutar `ffmpeg`: ```{str(e)[:1500]}```")
        return

    stdout = (out.decode(errors="ignore") or "").strip()
    stderr = (err.decode(errors="ignore") or "").strip()
    code = proc.returncode

    # Construir respuesta final con la info más útil (recortada si es muy larga)
    MAX_CHARS = 1800
    def trunc(s): return (s[:MAX_CHARS] + "...") if len(s) > MAX_CHARS else s

    if code == 0 and stdout:
        first_line = stdout.splitlines()[0]
        reply = (f"✅ `ffmpeg` encontrado en `{ff_path or 'desconocido'}`\n"
                 f"Versión (primer línea): `{first_line}`\n\n"
                 f"Salida completa (recortada si es larga):\n```{trunc(stdout)}```")
        print("ffmpeg OK:", first_line)
        try:
            await status_msg.edit(content=reply)
        except Exception:
            await interaction.followup.send(reply)
        return

    # Si llegamos aquí, algo no está bien: mostrar stdout/stderr y código
    reply_parts = [
        f"❌ `ffmpeg` ejecutado pero devolvió código {code}.",
        f"Ruta (shutil.which): `{ff_path}`"
    ]
    if stdout:
        reply_parts.append(f"Stdout (recortado):\n```{trunc(stdout)}```")
    if stderr:
        reply_parts.append(f"Stderr (recortado):\n```{trunc(stderr)}```")
    final_reply = "\n".join(reply_parts)

    print("ffmpeg check: exit code", code)
    print("stdout:", stdout)
    print("stderr:", stderr)
    try:
        await status_msg.edit(content=final_reply)
    except Exception:
        await interaction.followup.send(final_reply)


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
    
    if bot.user in message.mentions and not message.reference:
        # Responder usando IA
        try:
            reply = IA.chat(f"{message.content}")
        except Exception as e:
            reply = f"Locutor: Se le fundio la cabeza, no puede responder. Intenta llamar a Fenix, ERROR {e}"
        await message.reply(f"{reply}")
    
    try:
        await bot.process_commands(message)
    except Exception:
        # Si tu bot es discord.Client con app_commands y no usas process_commands, omite esto
        pass

#@bot.check
#async def global_check(ctx):
    #return

bot.run(DISCORD_TOKEN)



































