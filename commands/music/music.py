# cogs/music.py
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from collections import deque
import traceback # <-- ¡IMPORTANTE PARA VER ERRORES DETALLADOS!

# --- Funciones de Ayuda y Clase de Error ---

class YTDLError(Exception):
    """Excepción personalizada para errores de yt-dlp."""
    pass

async def search_ytdlp_async(query, ydl_opts):
    """Busca información de YouTube de forma asíncrona para no bloquear el bot."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    """Función síncrona que usa yt-dlp para extraer info."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            # Si es una lista de resultados (de una búsqueda), devolver la lista.
            # Si es un solo resultado (de una URL), devolver el diccionario de info.
            if "entries" in info:
                return info["entries"]
            return info
    except Exception as e:
        raise YTDLError(str(e))

####################################################################################

# --- El Cog de Música ---

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # La cola de canciones se adjunta a la instancia del bot.
        if not hasattr(bot, 'song_queues'):
            bot.song_queues = {}
        
        # NOTA: Asume que 'ffmpeg' está en el PATH de tu sistema.
        # Si no, reemplaza "ffmpeg" con la ruta completa a tu ejecutable.
        self.ffmpeg_path = "ffmpeg" 

    # --- COMANDOS DE BARRA ---

    @app_commands.command(name="play", description="Reproduce una canción o la añade a la cola.")
    @app_commands.describe(song_query="Término de búsqueda para YouTube o URL.")
    async def play(self, interaction: discord.Interaction, song_query: str):
        """Reproduce una canción con un registro detallado para depurar errores."""
        print(f"[MUSIC DEBUG] Comando /play recibido: '{song_query}' por {interaction.user.name}")

        # --- SUPER-RED DE SEGURIDAD ---
        try:
            # 1. Diferir la respuesta
            print("[MUSIC DEBUG] Intentando hacer 'defer'...")
            await interaction.response.defer()
            print("[MUSIC DEBUG] 'defer' exitoso.")

            # 2. Verificar canal de voz
            if not interaction.user.voice or not interaction.user.voice.channel:
                print("[MUSIC DEBUG] Usuario no está en un canal de voz.")
                return await interaction.followup.send("Debes estar en un canal de voz.", ephemeral=True)
            # Si llegamos aquí, es seguro que el usuario está en un canal
            voice_channel = interaction.user.voice.channel
            voice_client = interaction.guild.voice_client

            # 3. Conectar al canal de voz
            voice_client = interaction.guild.voice_client
            if voice_client is None:
                print(f"[MUSIC DEBUG] Conectando al canal {voice_channel.name}...")
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                print(f"[MUSIC DEBUG] Moviendo al canal {voice_channel.name}...")
                await voice_client.move_to(voice_channel)

            # 4. Buscar la canción con yt-dlp
            guild_id = interaction.guild.id
            if self.bot.song_queues.get(guild_id) is None:
                self.bot.song_queues[guild_id] = deque()

            ydl_options = {
                'format': 'bestaudio[abr<=96]/bestaudio',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            }

            query = song_query if "youtube.com/watch?v=" in song_query else f"ytsearch1:{song_query}"
            if "youtube.com/watch?v=" in song_query:
                print(f"[MUSIC DEBUG] Procesando URL directa: {query}")
            else:
                print(f"[MUSIC DEBUG] Procesando BÚSQUEDA: {query}")
            
            results = await search_ytdlp_async(query, ydl_options)
            print("[MUSIC DEBUG] Búsqueda de yt-dlp completada.")

            if not results:
                return await interaction.followup.send("No se encontraron resultados.", ephemeral=True)

            track = results[0] if isinstance(results, list) else results
            audio_url = track['url']
            title = track.get('title', 'Título no encontrado')
            print(f"[MUSIC DEBUG] Canción encontrada: '{title}'")

            self.bot.song_queues[guild_id].append((audio_url, title))

            # 5. Responder al usuario y reproducir
            if voice_client.is_playing() or voice_client.is_paused():
                await interaction.followup.send(f"✅ Añadido a la cola: **{title}**")
            else:
                await interaction.followup.send(f"🎶 Reproduciendo ahora: **{title}**")
                guild_id = interaction.guild.id
                channel = interaction.channel
                
                # Llamamos a la función con los argumentos correctos
                await self._play_next_song(voice_client, guild_id, channel)


        # --- ATRAPA CUALQUIER ERROR ---
        except Exception as e:
            print(f"[MUSIC ERROR] ERROR CRÍTICO CAPTURADO: {e}\n{traceback.format_exc()}")
            try:
                # Intenta informar al usuario del error
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Ocurrió un error crítico: `{e}`", ephemeral=True)
                else:
                    await interaction.followup.send(f"Ocurrió un error crítico: `{e}`", ephemeral=True)
            except Exception as e2:
                print(f"[MUSIC ERROR] No se pudo informar al usuario del error: {e2}")
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

    async def _play_next_song(self, voice_client, guild_id, channel: discord.TextChannel):
        """Función interna para reproducir la siguiente canción de la cola."""
        print(f"[MUSIC DEBUG] Reproduciendo siguiente canción para el guild {guild_id}...")
        
        if not self.bot.song_queues[guild_id]:
            print("[MUSIC DEBUG] La cola está vacía. Desconectando.")
            await voice_client.disconnect()
            self.bot.song_queues[guild_id].clear()
            try:
                await channel.send("📭 La cola ha terminado. Me desconectaré.")
            except Exception as e:
                print(f"[MUSIC ERROR] No pude enviar mensaje de fin de cola: {e}")
            return

        audio_url, title = self.bot.song_queues[guild_id].popleft()
        print(f"[MUSIC DEBUG] Extraído de la cola: '{title}'")

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -c:a libopus -b:a 96k',
            'executable': self.ffmpeg_path,
        }

        try:
            source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options)
        except Exception as e:
            print(f"[MUSIC ERROR] Fallo crítico al crear FFmpegOpusAudio: {e}\n{traceback.format_exc()}")
            # Si falla la creación del audio, pasa a la siguiente canción
            return await self._play_next_song(voice_client, guild_id, channel)

        def after_play(error):
            print(f"[MUSIC DEBUG] Callback 'after_play' ejecutado. Error: {error}")
            if error:
                print(f"[MUSIC ERROR] Error en la reproducción: {error}")
            
            # Llamar a la siguiente canción de forma segura desde otro hilo
            coro = self._play_next_song(voice_client, guild_id, channel)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                fut.result(timeout=60) # Añadir un timeout al futuro
            except Exception as e:
                print(f"[MUSIC ERROR] Error al programar la siguiente canción: {e}")

        try:
            voice_client.play(source, after=after_play)
            # Enviamos el mensaje de "now playing" como una tarea para no bloquear
            asyncio.create_task(channel.send(f"🎶 Reproduciendo ahora: **{title}**"))
        except Exception as e:
            print(f"[MUSIC ERROR] Fallo al ejecutar voice_client.play: {e}\n{traceback.format_exc()}")

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))