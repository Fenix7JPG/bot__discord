import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from collections import deque
import os
#discord.utils.setup_logging(level=discord.utils.logging.INFO)

from utils.ffmpeg_path import FFMPEG_PATH
from utils.cookies_path import COOKIES_PATH
# ─── yt-dlp config ────────────────────────────────────────────────────────────
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "quiet": False,
    "verbose": True,
    "extractaudio": True,
    "default_search": "scsearch",
    "cookiefile": COOKIES_PATH,
    "socket_timeout": 15,
    "retries": 3,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    },
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -protocol_whitelist file,http,https,tcp,tls,crypto,hls,data,m3u8",
    "options": "-vn -bufsize 64k",
}

# ─── Track ────────────────────────────────────────────────────────────────────
class Track:
    def __init__(self, title: str, page_url: str, duration: int, requester: discord.Member):
        self.title     = title
        self.page_url  = page_url
        self.duration  = duration
        self.requester = requester

    @property
    def duration_fmt(self) -> str:
        m, s = divmod(int(self.duration), 60)
        return f"{m}:{s:02d}"


async def resolve_track(query: str, requester: discord.Member) -> Track:
    """Busca en SoundCloud y devuelve un Track."""
    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            q = query if query.startswith("http") else f"scsearch:{query}"
            info = ydl.extract_info(q, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return Track(
                title=info.get("title", "Desconocido"),
                page_url=info.get("webpage_url", query),
                duration=info.get("duration", 0),
                requester=requester,
            )

    return await loop.run_in_executor(None, _extract)


async def get_audio_url(track: Track) -> str:
    """Resuelve y devuelve la URL de audio fresca para un Track."""
    loop = asyncio.get_event_loop()

    def _extract():
        opts = {**YTDL_OPTIONS, "format": "http_mp3_1_0/hls_mp3_1_0/hls_opus_0_0"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(track.page_url, download=False)
            if "entries" in info:
                info = info["entries"][0]

            # Usar directamente la URL del info, sin buscar en formats[]
            audio_url = info.get("url")
            if not audio_url:
                raise ValueError("No se encontró URL de audio")

            print(f"[DEBUG] URL final: {audio_url[:80]}")
            return audio_url

    return await loop.run_in_executor(None, _extract)


# ─── Embeds ───────────────────────────────────────────────────────────────────
def embed_now_playing(track: Track) -> discord.Embed:
    embed = discord.Embed(
        title="▶️  Reproduciendo ahora",
        description=f"**[{track.title}]({track.page_url})**",
        color=0xFF5500,
    )
    embed.add_field(name="Duración", value=track.duration_fmt, inline=True)
    embed.add_field(name="Solicitado por", value=track.requester.display_name, inline=True)
    embed.set_footer(text="SoundCloud 🔊  •  /queue  •  /skip  •  /stop")
    return embed


def embed_added_to_queue(track: Track, position: int) -> discord.Embed:
    embed = discord.Embed(
        title="➕  Añadido a la cola",
        description=f"**[{track.title}]({track.page_url})**",
        color=0xFF5500,
    )
    embed.add_field(name="Duración", value=track.duration_fmt, inline=True)
    embed.add_field(name="Posición en cola", value=str(position), inline=True)
    embed.add_field(name="Solicitado por", value=track.requester.display_name, inline=True)
    return embed


def embed_queue(queue: deque, current: Track | None) -> discord.Embed:
    embed = discord.Embed(title="📋  Cola de reproducción", color=0xFF5500)
    if current:
        embed.add_field(
            name="▶️ Sonando ahora",
            value=f"**{current.title}** ({current.duration_fmt}) — {current.requester.display_name}",
            inline=False,
        )
    if queue:
        lines = []
        for i, t in enumerate(list(queue)[:10], 1):
            lines.append(f"`{i}.` {t.title} ({t.duration_fmt}) — {t.requester.display_name}")
        if len(queue) > 10:
            lines.append(f"... y {len(queue) - 10} más")
        embed.add_field(name="⏭️ Próximas", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="⏭️ Próximas", value="La cola está vacía.", inline=False)
    return embed


# ─── Estado por servidor ──────────────────────────────────────────────────────
class GuildState:
    def __init__(self):
        self.queue:        deque[Track]               = deque()
        self.current:      Track | None               = None
        self.text_channel: discord.TextChannel | None = None
        self.stop_flag:    bool                       = False
        self._playing_lock: asyncio.Lock              = asyncio.Lock()


# ─── Cog ─────────────────────────────────────────────────────────────────────
class Play(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildState] = {}

    def _state(self, guild_id: int) -> GuildState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildState()
        return self._states[guild_id]

    # ── Reproducción interna ─────────────────────────────────────────────────

    async def _play_next(self, vc: discord.VoiceClient):
        guild_id = vc.guild.id
        state    = self._state(guild_id)

        if state._playing_lock.locked():
            return

        async with state._playing_lock:
            while True:
                if state.stop_flag:
                    return

                if not state.queue:
                    state.current = None
                    await self._announce(state, "⏹️ La cola terminó. ¡Hasta luego!")
                    try:
                        await vc.disconnect()
                    except Exception:
                        pass
                    return

                track         = state.queue.popleft()
                state.current = track

                try:
                    audio_url = await get_audio_url(track)
                    print(f"[DEBUG] Audio URL: {audio_url[:100]}")
                except Exception as e:
                    print(f"[Music] No pude resolver audio de '{track.title}': {e}")
                    await self._announce(state, f"⚠️ No pude reproducir **{track.title}**, saltando...")
                    continue

                done_event = asyncio.Event()

                def after(err):
                    if err:
                        print(f"[Music] Error FFmpeg: {err}")
                    self.bot.loop.call_soon_threadsafe(done_event.set)

                try:
                    source = discord.FFmpegPCMAudio(
                        audio_url,
                        executable=FFMPEG_PATH,
                        **FFMPEG_OPTIONS,
                    )
                    print(f"[DEBUG] FFmpeg path: {FFMPEG_PATH}")
                    print(f"[DEBUG] FFmpeg existe: {os.path.isfile(FFMPEG_PATH)}")
                    source = discord.PCMVolumeTransformer(source, volume=0.8)
                    vc.play(source, after=after)
                except Exception as e:
                    print(f"[Music] Error al iniciar FFmpeg para '{track.title}': {e}")
                    await self._announce(state, f"⚠️ Error de audio en **{track.title}**, saltando...")
                    continue

                await self._announce(state, embed=embed_now_playing(track))
                await done_event.wait()

                if state.stop_flag:
                    return

    async def _announce(self, state: GuildState, text: str = None, embed: discord.Embed = None):
        if state.text_channel:
            try:
                await state.text_channel.send(content=text, embed=embed)
            except Exception:
                pass

    async def _ensure_connected(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Debes estar en un canal de voz primero.", ephemeral=True)
            return None

        channel = interaction.user.voice.channel
        vc: discord.VoiceClient | None = interaction.guild.voice_client

        try:
            if vc is None:
                vc = await channel.connect(timeout=20.0)
            elif vc.channel.id != channel.id:
                await vc.move_to(channel)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ No pude conectarme al canal (timeout).", ephemeral=True)
            return None
        except Exception as e:
            await interaction.followup.send(f"❌ Error al conectar: {e}", ephemeral=True)
            return None

        return vc

    # ── Comandos ─────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="▶️ Reproduce o encola una canción de SoundCloud")
    @app_commands.describe(query="URL de SoundCloud o búsqueda (ej: 'lofi chill beats')")
    async def play_cmd(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        try:
            track = await resolve_track(query, interaction.user)
        except Exception as e:
            await interaction.followup.send(f"❌ No encontré nada: `{e}`", ephemeral=True)
            return

        vc = await self._ensure_connected(interaction)
        if vc is None:
            return

        state              = self._state(interaction.guild.id)
        state.text_channel = interaction.channel
        state.stop_flag    = False

        if vc.is_playing() or vc.is_paused():
            state.queue.append(track)
            await interaction.followup.send(embed=embed_added_to_queue(track, len(state.queue)))
        else:
            state.queue.append(track)
            await interaction.followup.send(f"🔍 Cargando **{track.title}**...")
            asyncio.create_task(self._play_next(vc))

    @app_commands.command(name="skip", description="⏭️ Salta la canción actual")
    async def skip_cmd(self, interaction: discord.Interaction):
        vc: discord.VoiceClient | None = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message("❌ No hay nada sonando.", ephemeral=True)
            return
        await interaction.response.send_message("⏭️ Saltando...")
        vc.stop()

    @app_commands.command(name="stop", description="⏹️ Detiene la música, limpia la cola y desconecta")
    async def stop_cmd(self, interaction: discord.Interaction):
        vc: discord.VoiceClient | None = interaction.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message("❌ No estoy en ningún canal de voz.", ephemeral=True)
            return

        await interaction.response.defer()
        state           = self._state(interaction.guild.id)
        state.stop_flag = True
        state.queue.clear()
        state.current   = None
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await vc.disconnect()
        await interaction.followup.send("⏹️ Música detenida. ¡Hasta luego!")

    @app_commands.command(name="queue", description="📋 Muestra la cola de reproducción")
    async def queue_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        state = self._state(interaction.guild.id)
        await interaction.followup.send(embed=embed_queue(state.queue, state.current))

    @app_commands.command(name="nowplaying", description="🎵 Muestra la canción actual")
    async def nowplaying_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        state = self._state(interaction.guild.id)
        if not state.current:
            await interaction.followup.send("❌ No hay nada sonando.", ephemeral=True)
            return
        await interaction.followup.send(embed=embed_now_playing(state.current))

    @app_commands.command(name="pause", description="⏸️ Pausa la reproducción")
    async def pause_cmd(self, interaction: discord.Interaction):
        vc: discord.VoiceClient | None = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Pausado.")
        else:
            await interaction.response.send_message("❌ No hay nada sonando.", ephemeral=True)

    @app_commands.command(name="resume", description="▶️ Reanuda la reproducción")
    async def resume_cmd(self, interaction: discord.Interaction):
        vc: discord.VoiceClient | None = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Reanudando.")
        else:
            await interaction.response.send_message("❌ No hay nada pausado.", ephemeral=True)

    @app_commands.command(name="clearqueue", description="🗑️ Limpia la cola sin detener la canción actual")
    async def clearqueue_cmd(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        state.queue.clear()
        await interaction.response.send_message("🗑️ Cola limpiada.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Play(bot))