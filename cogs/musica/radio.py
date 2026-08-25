"""Cog de radio: streams en vivo 24/7 con reconexion automatica."""

import asyncio
import os
import shutil

import discord
from discord import app_commands
from discord.ext import commands


FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

# Estaciones predefinidas para /playradio <nombre>. Se pueden agregar o quitar
# entradas aqui sin tocar nada mas.
STATIONS = {
    "lofi": {"name": "Lofi Hip Hop", "url": "https://streams.ilovemusic.de/iloveradio17.mp3", "emoji": "🎵"},
    "chillpop": {"name": "Chill Pop", "url": "https://streams.ilovemusic.de/iloveradio2.mp3", "emoji": "☁️"},
    "jazz": {"name": "Jazz Cafe", "url": "https://streams.ilovemusic.de/iloveradio21.mp3", "emoji": "🎷"},
    "ambient": {"name": "Ambient & Study", "url": "https://streams.ilovemusic.de/iloveradio26.mp3", "emoji": "🌙"},
    "clasica": {"name": "Clasica", "url": "https://streams.ilovemusic.de/iloveradio6.mp3", "emoji": "🎻"},
    "deephouse": {"name": "Deep House", "url": "https://streams.ilovemusic.de/iloveradio13.mp3", "emoji": "🎧"},
}


def embed_now_playing(nombre: str, url: str, autor: discord.Member) -> discord.Embed:
    embed = discord.Embed(title="Reproduciendo ahora", description="**" + nombre + "**", color=0x9B59B6)
    embed.add_field(name="Stream", value="24/7 en vivo", inline=True)
    embed.add_field(name="Pedida por", value=autor.display_name, inline=True)
    embed.add_field(name="URL", value=url, inline=False)
    return embed


class PlayRadio(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.url_actual: dict[int, str] = {}     # guild_id -> url sonando
        self.nombre_actual: dict[int, str] = {}  # guild_id -> nombre visible
        self.reconectando: set[int] = set()

    # -- internos -------------------------------------------------------------

    def _reproducir_url(self, vc: discord.VoiceClient, url: str, nombre: str):
        guild_id = vc.guild.id

        # Marcar que este stop es intencional (cambio de estacion), no un corte
        self.reconectando.discard(guild_id)
        self.url_actual[guild_id] = url
        self.nombre_actual[guild_id] = nombre

        if vc.is_playing() or vc.is_paused():
            vc.stop()

        def after(err):
            # Reconectar solo si fue un error real y nadie cambio la estacion
            if err is None:
                return
            if guild_id in self.reconectando:
                return
            if not vc.is_connected() or self.url_actual.get(guild_id) != url:
                return
            self.reconectando.add(guild_id)
            asyncio.run_coroutine_threadsafe(self._reconectar(vc, url, nombre), self.bot.loop)

        fuente = discord.FFmpegPCMAudio(
            url,
            executable=FFMPEG_PATH,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
        )
        vc.play(fuente, after=after)

    async def _reconectar(self, vc: discord.VoiceClient, url: str, nombre: str):
        await asyncio.sleep(2)
        guild_id = vc.guild.id
        if vc.is_connected() and self.url_actual.get(guild_id) == url:
            print("[radio] reconectando a", nombre)
            self._reproducir_url(vc, url, nombre)
        self.reconectando.discard(guild_id)

    async def _conectar(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
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

    # -- comandos ---------------------------------------------------------------

    @app_commands.command(name="playradio", description="Reproduce un stream: nombre de estacion o URL.")
    @app_commands.describe(url="Nombre de estacion (lofi, jazz...) o URL directa del stream")
    async def playradio(self, interaction: discord.Interaction, url: str = "lofi"):
        await interaction.response.defer()

        if url in STATIONS:
            estacion = STATIONS[url]
            stream_url = estacion["url"]
            nombre = estacion["emoji"] + " " + estacion["name"]
        else:
            stream_url = url
            nombre = "Stream personalizado"

        vc = await self._conectar(interaction)
        if vc is None:
            return

        self._reproducir_url(vc, stream_url, nombre)
        await interaction.followup.send(embed=embed_now_playing(nombre, stream_url, interaction.user))

    @app_commands.command(name="stopradio", description="Detiene la radio y desconecta al bot.")
    async def stopradio(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message("No estoy en ningun canal de voz.", ephemeral=True)
            return

        self.url_actual.pop(interaction.guild.id, None)
        self.nombre_actual.pop(interaction.guild.id, None)
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await vc.disconnect()
        await interaction.response.send_message("Radio detenida. Hasta luego.")

    @app_commands.command(name="nowplayingradio", description="Muestra que esta sonando.")
    async def nowplayingradio(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        guild_id = interaction.guild.id

        if vc is None or not vc.is_connected() or not vc.is_playing():
            await interaction.followup.send("No hay nada sonando. Usa /playradio para iniciar.", ephemeral=True)
            return

        url = self.url_actual.get(guild_id, "?")
        nombre = self.nombre_actual.get(guild_id, "Desconocido")
        await interaction.followup.send(embed=embed_now_playing(nombre, url, interaction.user))

    @app_commands.command(name="stations", description="Lista las estaciones predefinidas.")
    async def stations(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="Estaciones predefinidas",
            description="Usalas con /playradio <nombre> o pasa cualquier URL directamente.",
            color=0x9B59B6,
        )
        for clave, estacion in STATIONS.items():
            embed.add_field(
                name=estacion["emoji"] + " " + estacion["name"],
                value="`" + clave + "`",
                inline=True,
            )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayRadio(bot))
