"""Cog /play: musica desde SoundCloud con cola por servidor."""

import asyncio
import os
import shutil
from collections import deque

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands


# Ruta de FFmpeg: el binario instalado en el sistema o "ffmpeg" y que el
# sistema lo resuelva.
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

# Opciones base de yt-dlp. Las cookies se añaden solo si el archivo existe
# (en local normalmente no hay; en Render puede montarse como Secret File).
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "scsearch",
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

_cookies_file = os.getenv("YT_COOKIES_FILE", "/etc/secrets/cookies.txt")
if os.path.exists(_cookies_file):
    YTDL_OPTIONS["cookiefile"] = _cookies_file

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class Track:
    """Cancion en la cola."""

    def __init__(self, titulo: str, url_pagina: str, duracion: int, autor: discord.Member):
        self.titulo = titulo
        self.url_pagina = url_pagina
        self.duracion = duracion
        self.autor = autor

    @property
    def duracion_texto(self) -> str:
        minutos, segundos = divmod(int(self.duracion), 60)
        return str(minutos) + ":" + format(segundos, "02d")


def embed_reproduciendo(track: Track) -> discord.Embed:
    embed = discord.Embed(
        title="Reproduciendo ahora",
        description="**[" + track.titulo + "](" + track.url_pagina + ")**",
        color=0xFF5500,
    )
    embed.add_field(name="Duracion", value=track.duracion_texto, inline=True)
    embed.add_field(name="Pedida por", value=track.autor.display_name, inline=True)
    return embed


def embed_cola(cola: deque, actual: Track | None) -> discord.Embed:
    embed = discord.Embed(title="Cola de reproduccion", color=0xFF5500)
    if actual is not None:
        embed.add_field(
            name="Sonando ahora",
            value="**" + actual.titulo + "** (" + actual.duracion_texto + ") - " + actual.autor.display_name,
            inline=False,
        )
    if cola:
        lineas = []
        for i, track in enumerate(list(cola)[:10], start=1):
            lineas.append(str(i) + ". " + track.titulo + " (" + track.duracion_texto + ")")
        if len(cola) > 10:
            lineas.append("... y " + str(len(cola) - 10) + " mas")
        embed.add_field(name="Siguientes", value="\n".join(lineas), inline=False)
    else:
        embed.add_field(name="Siguientes", value="La cola esta vacia.", inline=False)
    return embed


class GuildState:
    """Estado musical de un servidor: cola, cancion actual y canal de avisos."""

    def __init__(self):
        self.cola: deque[Track] = deque()
        self.actual: Track | None = None
        self.canal_texto: discord.TextChannel | None = None
        self.detener = False
        self.lock_reproduccion = asyncio.Lock()


class Play(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.estados: dict[int, GuildState] = {}

    def estado(self, guild_id: int) -> GuildState:
        if guild_id not in self.estados:
            self.estados[guild_id] = GuildState()
        return self.estados[guild_id]

    # -- busqueda y audio ----------------------------------------------------

    async def resolver_track(self, consulta: str, autor: discord.Member) -> Track:
        """Busca en SoundCloud (o usa la URL directa) y devuelve un Track."""
        loop = asyncio.get_event_loop()

        def _extraer():
            opciones = dict(YTDL_OPTIONS)
            with yt_dlp.YoutubeDL(opciones) as ydl:
                q = consulta if consulta.startswith("http") else "scsearch:" + consulta
                info = ydl.extract_info(q, download=False)
                if "entries" in info:
                    info = info["entries"][0]
                return Track(
                    titulo=info.get("title", "Desconocido"),
                    url_pagina=info.get("webpage_url", consulta),
                    duracion=info.get("duration", 0),
                    autor=autor,
                )

        return await loop.run_in_executor(None, _extraer)

    async def obtener_url_audio(self, track: Track) -> str:
        """Resuelve la URL de audio fresca de la pista."""
        loop = asyncio.get_event_loop()

        def _extraer():
            with yt_dlp.YoutubeDL(dict(YTDL_OPTIONS)) as ydl:
                info = ydl.extract_info(track.url_pagina, download=False)
                if "entries" in info:
                    info = info["entries"][0]
                url = info.get("url")
                if not url:
                    for formato in reversed(info.get("formats") or []):
                        if formato.get("url") and formato.get("acodec", "none") != "none":
                            url = formato["url"]
                            break
                if not url:
                    raise ValueError("Sin URL de audio para " + track.titulo)
                return url

        return await loop.run_in_executor(None, _extraer)

    # -- bucle interno -------------------------------------------------------

    async def _reproducir_siguiente(self, vc: discord.VoiceClient):
        estado = self.estado(vc.guild.id)

        if estado.lock_reproduccion.locked():
            return

        async with estado.lock_reproduccion:
            while True:
                if estado.detener:
                    return

                if not estado.cola:
                    estado.actual = None
                    await self._avisar(estado, "La cola termino. Hasta luego.")
                    try:
                        await vc.disconnect()
                    except Exception:
                        pass
                    return

                track = estado.cola.popleft()
                estado.actual = track

                try:
                    url_audio = await self.obtener_url_audio(track)
                except Exception as e:
                    print("[musica] sin audio para", track.titulo, ":", e)
                    await self._avisar(estado, "No pude reproducir **" + track.titulo + "**, salto a la siguiente.")
                    continue

                fin_evento = asyncio.Event()

                def after(err, _fin=fin_evento):
                    self.bot.loop.call_soon_threadsafe(_fin.set)

                try:
                    fuente = discord.FFmpegPCMAudio(
                        url_audio, executable=FFMPEG_PATH, **FFMPEG_OPTIONS
                    )
                    fuente = discord.PCMVolumeTransformer(fuente, volume=0.8)
                    vc.play(fuente, after=after)
                except Exception as e:
                    print("[musica] error iniciando FFmpeg:", e)
                    await self._avisar(estado, "Error de audio en **" + track.titulo + "**, salto a la siguiente.")
                    continue

                await self._avisar(estado, embed=embed_reproduciendo(track))
                await fin_evento.wait()

                if estado.detener:
                    return

    async def _avisar(self, estado: GuildState, texto: str = None, embed: discord.Embed = None):
        if estado.canal_texto is not None:
            try:
                await estado.canal_texto.send(content=texto, embed=embed)
            except Exception:
                pass

    async def _conectar(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        """Conecta al canal de voz del usuario o mueve al bot si ya estaba."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("Debes estar en un canal de voz primero.", ephemeral=True)
            return None

        canal = interaction.user.voice.channel
        vc = interaction.guild.voice_client
        try:
            if vc is None:
                vc = await canal.connect(timeout=20.0)
            elif vc.channel.id != canal.id:
                await vc.move_to(canal)
        except Exception as e:
            await interaction.followup.send("No pude conectarme al canal: " + str(e), ephemeral=True)
            return None
        return vc

    # -- comandos --------------------------------------------------------------

    @app_commands.command(name="play", description="Reproduce o encola una cancion de SoundCloud.")
    @app_commands.describe(query="URL de SoundCloud o texto de busqueda")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        try:
            track = await self.resolver_track(query, interaction.user)
        except Exception as e:
            await interaction.followup.send("No encontre nada: " + str(e), ephemeral=True)
            return

        vc = await self._conectar(interaction)
        if vc is None:
            return

        estado = self.estado(interaction.guild.id)
        estado.canal_texto = interaction.channel
        estado.detener = False
        estado.cola.append(track)

        if vc.is_playing() or vc.is_paused():
            await interaction.followup.send(
                "Añadido a la cola: **" + track.titulo + "** (posicion " + str(len(estado.cola)) + ")"
            )
        else:
            await interaction.followup.send("Cargando **" + track.titulo + "**...")
            asyncio.create_task(self._reproducir_siguiente(vc))

    @app_commands.command(name="skip", description="Salta la cancion actual.")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message("No hay nada sonando.", ephemeral=True)
            return
        await interaction.response.send_message("Saltando...")
        vc.stop()

    @app_commands.command(name="stop", description="Detiene la musica, limpia la cola y desconecta.")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message("No estoy en ningun canal de voz.", ephemeral=True)
            return

        await interaction.response.defer()
        estado = self.estado(interaction.guild.id)
        estado.detener = True
        estado.cola.clear()
        estado.actual = None
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await vc.disconnect()
        await interaction.followup.send("Musica detenida. Hasta luego.")

    @app_commands.command(name="queue", description="Muestra la cola de reproduccion.")
    async def queue(self, interaction: discord.Interaction):
        await interaction.response.defer()
        estado = self.estado(interaction.guild.id)
        await interaction.followup.send(embed=embed_cola(estado.cola, estado.actual))

    @app_commands.command(name="nowplaying", description="Muestra la cancion actual.")
    async def nowplaying(self, interaction: discord.Interaction):
        await interaction.response.defer()
        estado = self.estado(interaction.guild.id)
        if estado.actual is None:
            await interaction.followup.send("No hay nada sonando.", ephemeral=True)
            return
        await interaction.followup.send(embed=embed_reproduciendo(estado.actual))

    @app_commands.command(name="pause", description="Pausa la reproduccion.")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is not None and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("Pausado.")
        else:
            await interaction.response.send_message("No hay nada sonando.", ephemeral=True)

    @app_commands.command(name="resume", description="Reanuda la reproduccion.")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is not None and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("Reanudando.")
        else:
            await interaction.response.send_message("No hay nada pausado.", ephemeral=True)

    @app_commands.command(name="clearqueue", description="Limpia la cola sin detener la cancion actual.")
    async def clearqueue(self, interaction: discord.Interaction):
        estado = self.estado(interaction.guild.id)
        estado.cola.clear()
        await interaction.response.send_message("Cola limpiada.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Play(bot))
