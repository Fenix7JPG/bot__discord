import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# Logs
discord.utils.setup_logging(level=discord.utils.logging.INFO)

# ─── Estaciones predefinidas (solo para /stations) ───────────────────────────
# Agrega o quita entradas aquí libremente, sin tocar nada más.
STATIONS: dict[str, dict] = {
    "lofi": {
        "name":  "Lofi Hip Hop 📻",
        "url":   "https://streams.ilovemusic.de/iloveradio17.mp3",
        "emoji": "🎵",
        "color": 0x9B59B6,
    },
    "chillpop": {
        "name":  "Chill Pop ☁️",
        "url":   "https://streams.ilovemusic.de/iloveradio2.mp3",
        "emoji": "🌤️",
        "color": 0x3498DB,
    },
    "jazz": {
        "name":  "Jazz Café ☕",
        "url":   "https://streams.ilovemusic.de/iloveradio21.mp3",
        "emoji": "🎷",
        "color": 0xE67E22,
    },
    "ambient": {
        "name":  "Ambient & Study 🌙",
        "url":   "https://streams.ilovemusic.de/iloveradio26.mp3",
        "emoji": "🌙",
        "color": 0x2C3E50,
    },
    "clasica": {
        "name":  "Clásica 🎻",
        "url":   "https://streams.ilovemusic.de/iloveradio6.mp3",
        "emoji": "🎻",
        "color": 0xC0392B,
    },
    "deephouse": {
        "name":  "Deep House 🎧",
        "url":   "https://streams.ilovemusic.de/iloveradio13.mp3",
        "emoji": "🎧",
        "color": 0x1ABC9C,
    },
}

# Ajusta si ffmpeg no está en el PATH
from utils.ffmpeg_path import FFMPEG_PATH


def _make_now_playing_embed(name: str, url: str, requester: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="🎵  Reproduciendo ahora",
        description=f"**{name}**",
        color=0x9B59B6,
    )
    embed.add_field(name="Stream", value="24/7 en vivo 🔴", inline=True)
    embed.add_field(name="Solicitado por", value=requester.display_name, inline=True)
    embed.add_field(name="URL", value=f"`{url}`", inline=False)
    embed.set_footer(text="Usa /playradio <url> para cambiar stream • /stop para detener")
    return embed


class PlayRadio(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._current_url: dict[int, str] = {}   # guild_id → url activa
        self._current_name: dict[int, str] = {}  # guild_id → nombre para mostrar
        self._reconnecting: set[int] = set()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _play_url(self, vc: discord.VoiceClient, url: str, name: str):
        guild_id = vc.guild.id

        # Marcar que el stop que viene es intencional, no un corte de red
        self._reconnecting.discard(guild_id)
        self._current_url[guild_id] = url
        self._current_name[guild_id] = name

        if vc.is_playing() or vc.is_paused():
            vc.stop()

        def after(err):
            # Solo reconectar si fue un error real (err no es None)
            # y nadie cambió la estación mientras tanto
            if err is None:
                return
            if guild_id in self._reconnecting:
                return
            if not vc.is_connected() or guild_id not in self._current_url:
                return
            if self._current_url[guild_id] != url:
                return  # ya se cambió a otra estación, no reconectar
            saved_url = self._current_url[guild_id]
            saved_name = self._current_name[guild_id]
            self._reconnecting.add(guild_id)
            asyncio.run_coroutine_threadsafe(
                self._reconnect(vc, saved_url, saved_name), self.bot.loop
            )

        source = discord.FFmpegPCMAudio(
            url,
            executable=FFMPEG_PATH,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
        )
        vc.play(source, after=after)

    async def _reconnect(self, vc: discord.VoiceClient, url: str, name: str):
        await asyncio.sleep(2)
        guild_id = vc.guild.id
        if vc.is_connected() and guild_id in self._current_url:
            if self._current_url[guild_id] == url:
                print(f"[Lofi] Reconectando a {name}...")
                self._play_url(vc, url, name)
        self._reconnecting.discard(guild_id)

    async def _ensure_connected(
        self, interaction: discord.Interaction
    ) -> discord.VoiceClient | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(
                "❌ Debes estar en un canal de voz primero.", ephemeral=True
            )
            return None

        channel = interaction.user.voice.channel
        vc: discord.VoiceClient | None = interaction.guild.voice_client

        try:
            if vc is None:
                vc = await channel.connect(timeout=20.0)
            elif vc.channel.id != channel.id:
                await vc.move_to(channel)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "❌ No pude conectarme al canal (timeout).", ephemeral=True
            )
            return None
        except Exception as e:
            await interaction.followup.send(f"❌ Error al conectar: {e}", ephemeral=True)
            return None

        return vc

    # ── Comandos ──────────────────────────────────────────────────────────────

    @app_commands.command(name="playradio", description="▶️ Reproduce un stream — pasa una URL o el nombre de una estación")
    @app_commands.describe(url="URL del stream MP3/AAC, o nombre de estación: lofi, jazz, ambient, chillpop…")
    async def lofi_cmd(
        self,
        interaction: discord.Interaction,
        url: str = "lofi",
    ):
        await interaction.response.defer()

        # Resolver nombre de estación predefinida → URL real
        if url in STATIONS:
            station = STATIONS[url]
            stream_url = station["url"]
            name = f"{station['emoji']} {station['name']}"
        else:
            # Tratar como URL directa
            stream_url = url
            name = "Stream personalizado 🎙️"

        vc = await self._ensure_connected(interaction)
        if vc is None:
            return

        self._play_url(vc, stream_url, name)
        embed = _make_now_playing_embed(name, stream_url, interaction.user)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stopradio", description="⏹️ Detiene la radio y desconecta al bot")
    async def stop_cmd(self, interaction: discord.Interaction):
        vc: discord.VoiceClient | None = interaction.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message(
                "❌ No estoy en ningún canal de voz.", ephemeral=True
            )
            return

        self._current_url.pop(interaction.guild.id, None)
        self._current_name.pop(interaction.guild.id, None)
        await vc.disconnect()
        await interaction.response.send_message("⏹️ Radio detenida. ¡Hasta luego!")

    @app_commands.command(name="nowplayingradio", description="🎵 Muestra qué está sonando")
    async def nowplaying_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()

        vc: discord.VoiceClient | None = interaction.guild.voice_client
        guild_id = interaction.guild.id

        if vc is None or not vc.is_connected() or not vc.is_playing():
            await interaction.followup.send(
                "❌ No hay nada sonando. Usa `/lofi` para iniciar.", ephemeral=True
            )
            return

        url = self._current_url.get(guild_id, "?")
        name = self._current_name.get(guild_id, "Desconocido")
        embed = _make_now_playing_embed(name, url, interaction.user)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stations", description="📻 Lista todas las estaciones predefinidas")
    async def stations_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(
            title="📻 Estaciones predefinidas",
            description="Úsalas con `/playradio <nombre>` o pasa cualquier URL directamente con `/playradio <url>`.",
            color=0x9B59B6,
        )
        for key, s in STATIONS.items():
            embed.add_field(
                name=f"{s['emoji']} {s['name']}",
                value=f"`{key}`",
                inline=True,
            )
        embed.set_footer(text="Ejemplo: /playradio jazz   •   /playradio https://mi-radio.com/stream.mp3")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayRadio(bot))