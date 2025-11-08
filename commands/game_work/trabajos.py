# cogs/trabajos.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio

# --- IMPORTA TUS UTILIDADES ---
# Asegúrate de que esta ruta sea correcta según tu estructura de proyecto
from ...utils.data import file_lock, PATH_TRABAJOS

# --- CONSTANTES (Pueden estar aquí o en tu Cog) ---
JOBS_PAGE_SIZE = 8
VIEW_TIMEOUT = 300  # segundos

# --- VISTA DE PAGINACIÓN (Ahora fuera del comando, para mayor limpieza) ---
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
        self.prev_button.disabled = (self.page == 0)
        self.next_button.disabled = (self.page == self.max_page)

    def build_embed(self):
        start = self.page * self.page_size
        end = start + self.page_size
        chunk = self.jobs[start:end]
        embed = discord.Embed(
            title="💼 Trabajos disponibles",
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

####################################################################################
# --- EL COG PRINCIPAL ---

class Trabajos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trabajos", description="Ver los trabajos disponibles.")
    async def trabajos(self, interaction: discord.Interaction):
        """Muestra una lista paginada de los trabajos disponibles."""
        await interaction.response.defer()

        # --- Leer archivo de trabajos (dentro de file_lock para seguridad) ---
        async with file_lock:
            def _read_sync():
                if not os.path.exists(PATH_TRABAJOS):
                    return None
                with open(PATH_TRABAJOS, "r", encoding="utf-8") as f:
                    try:
                        return json.load(f)
                    except json.JSONDecodeError:
                        return None
            raw = await asyncio.to_thread(_read_sync)

        if not raw:
            await interaction.followup.send("No hay trabajos disponibles o el archivo está mal formado.", ephemeral=True)
            return

        # --- Normalizar a lista de trabajos (lógica idéntica a la original) ---
        jobs_list = []
        if isinstance(raw, dict):
            maybe = raw.get("jobs")
            if isinstance(maybe, list):
                jobs_list = maybe
            elif all(isinstance(v, dict) for v in raw.values()):
                jobs_list = list(raw.values())
        elif isinstance(raw, list):
            jobs_list = raw

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

        # --- Crear y enviar la vista ---
        view = JobsView(norm_jobs, interaction.user.id, page_size=JOBS_PAGE_SIZE, timeout=VIEW_TIMEOUT)
        embed = view.build_embed()
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Trabajos(bot))