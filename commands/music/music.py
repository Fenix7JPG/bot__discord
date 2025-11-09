# cogs/music.py
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from collections import deque

# --- Funciones de Ayude (se quedan igual, pero fuera de la clase) ---

class YTDLError(Exception):
    pass

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" not in info:
                return info
            return info["entries"]
    except Exception as e:
        raise YTDLError(str(e))

####################################################################################

# --- El Cog de Música ---

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # CAMBIO CLAVE: La cola se adjunta a la instancia del bot, no es global.
        if not hasattr(bot, 'song_queues'):
            bot.song_queues = {}
        
        # NOTA: Asume que 'ffmpeg' está en el PATH de tu sistema.
        # Si no, reemplaza "ffmpeg" con la ruta completa a tu ejecutable.
        self.ffmpeg_path = "ffmpeg" 

    # --- COMANDOS DE BARRA ---

    @app_commands.command(name="play", description="Reproduce una canción o la añade a la cola.")
    @app_commands.describe(song_query="Término de búsqueda para YouTube o URL.")
    async def play(self, interaction: discord.Interaction, song_query: str):
        """Reproduce una canción."""
        await interaction.response.defer()

        voice_channel = interaction.user.voice.channel
        if not voice_channel:
            return await interaction.followup.send("Debes estar en un canal de voz.")

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        guild_id = interaction.guild.id
        if self.bot.song_queues.get(guild_id) is None:
            self.bot.song_queues[guild_id] = deque()

        ydl_options = {
            'format': 'bestaudio[abr<=96]/bestaudio',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }

        try:
            # Si es una URL, búscala directamente. Si no, búscala como término.
            query = song_query if "youtube.com/watch?v=" in song_query else f"ytsearch1:{song_query}"
            results = await search_ytdlp_async(query, ydl_options)

            if not results:
                return await interaction.followup.send("No se encontraron resultados.")

            # Si es una lista (de búsqueda), toma el primer elemento.
            track = results[0] if isinstance(results, list) else results
            audio_url = track['url']
            title = track.get('title', 'Título no encontrado')

            self.bot.song_queues[guild_id].append((audio_url, title))

            if voice_client.is_playing() or voice_client.is_paused():
                await interaction.followup.send(f"✅ Añadido a la cola: **{title}**")
            else:
                await interaction.followup.send(f"🎶 Reproduciendo ahora: **{title}**")
                await self._play_next_song(interaction)

        except YTDLError as e:
            await interaction.followup.send(f"Ocurrió un error al buscar la canción: {e}")
        except Exception as e:
            await interaction.followup.send(f"Ocurrió un error inesperado: {e}")

    @app_commands.command(name="skip", description="Salta la canción actual.")
    async def skip(self, interaction: discord.Interaction):
        """Salta a la siguiente canción."""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop() # Esto activará el callback 'after' y reproducirá la siguiente.
            await interaction.response.send_message("⏭️ Canción saltada.")
        else:
            await interaction.response.send_message("No hay nada reproduciéndose para saltar.", ephemeral=True)

    @app_commands.command(name="pause", description="Pausa la reproducción.")
    async def pause(self, interaction: discord.Interaction):
        """Pausa la canción actual."""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Reproducción pausada.")
        else:
            await interaction.response.send_message("No hay nada reproduciéndose.", ephemeral=True)

    @app_commands.command(name="resume", description="Reanuda la reproducción.")
    async def resume(self, interaction: discord.Interaction):
        """Reanuda la canción pausada."""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Reproducción reanudada.")
        else:
            await interaction.response.send_message("La reproducción no está pausada.", ephemeral=True)

    @app_commands.command(name="stop", description="Detiene la reproducción y limpia la cola.")
    async def stop(self, interaction: discord.Interaction):
        """Detiene la música y se desconecta."""
        voice_client = interaction.guild.voice_client
        if not voice_client:
            return await interaction.response.send_message("No estoy en un canal de voz.", ephemeral=True)
        
        guild_id = interaction.guild.id
        self.bot.song_queues[guild_id].clear()
        voice_client.stop()
        await voice_client.disconnect()
        await interaction.response.send_message("🛑 Música detenida y me he desconectado.")

    # --- LÓGICA INTERNA DEL COG ---

    async def _play_next_song(self, interaction: discord.Interaction):
        """Función interna para reproducir la siguiente canción de la cola."""
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        channel = interaction.channel

        if not self.bot.song_queues[guild_id]:
            await voice_client.disconnect()
            self.bot.song_queues[guild_id].clear()
            await channel.send("📭 La cola ha terminado. Me desconectaré.")
            return

        audio_url, title = self.bot.song_queues[guild_id].popleft()

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -c:a libopus -b:a 96k',
            'executable': self.ffmpeg_path,
        }

        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options)

        def after_play(error):
            if error:
                print(f"Error en la reproducción: {error}")
                # Usar run_coroutine_threadsafe para llamar a una corutina desde un hilo
                coro = self._play_next_song(interaction)
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"Error al programar la siguiente canción: {e}")
            else:
                # Si no hay error, continuar con la siguiente canción
                coro = self._play_next_song(interaction)
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"Error al programar la siguiente canción: {e}")

        voice_client.play(source, after=after_play)
        asyncio.create_task(channel.send(f"🎶 Reproduciendo ahora: **{title}**"))

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))