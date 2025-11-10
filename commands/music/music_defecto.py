# cogs/music.py
import discord
from discord.ext import commands
from discord import app_commands

class PlayF(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="playf", description="Reproduce una canción de prueba.")
    async def playf(self, interaction: discord.Interaction):
        """Reproduce una canción de prueba en tu canal de voz."""
        
        # 1. Verificar si el usuario está en un canal de voz
        voice_channel = interaction.user.voice.channel
        if not voice_channel:
            return await interaction.response.send_message("❌ Debes estar en un canal de voz.", ephemeral=True)

        # 2. Conectar al canal de voz
        try:
            voice_client = await voice_channel.connect()
        except discord.errors.ClientException:
            # Si ya está conectado, obtener el cliente de voz actual
            voice_client = interaction.guild.voice_client
            if not voice_client:
                return await interaction.response.send_message("❌ No pude conectarme.", ephemeral=True)

        # 3. Responder que estamos a punto de reproducir
        await interaction.response.send_message("🎶 Reproduciendo canción de prueba...")

        # 4. Definir la URL de la canción y las opciones de FFmpeg
        song_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        ffmpeg_options = {
            'options': '-vn -c:a libopus -b:a 96k',
            'executable': "ffmpeg" # Asegúrate de que ffmpeg esté en tu PATH
        }

        # 5. Crear la fuente de audio y reproducirla
        try:
            source = discord.FFmpegOpusAudio(song_url, **ffmpeg_options)
            voice_client.play(source)
        except Exception as e:
            print(f"Error al reproducir: {e}")
            await interaction.followup.send("❌ Ocurrió un error al intentar reproducir la canción.", ephemeral=True)

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(PlayF(bot))