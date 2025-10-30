# commands/ytmp3.py
import discord
from discord import app_commands
import yt_dlp
from io import BytesIO

def setup(tree: app_commands.CommandTree):

    @tree.command(name="ytmp3", description="Descarga música de YouTube y la envía como MP3 🎵")
    @app_commands.describe(query="Nombre o URL del video de YouTube")
    async def ytmp3(interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        
        # Configurar yt-dlp
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "outtmpl": "-",
            "postprocessors": [
                {  # convertir a mp3
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        try:
            buffer = BytesIO()

            # Hook para capturar la salida de audio en memoria
            def progress_hook(d):
                if d.get("status") == "finished":
                    print("✅ Descarga completada, convirtiendo a MP3...")

            ydl_opts["progress_hooks"] = [progress_hook]

            # Descargar y convertir directamente al buffer
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                url = info.get("url")

                # Volvemos a descargar el audio como stream binario
                import subprocess

                # ffmpeg convierte el stream directo sin tocar disco
                process = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-i", url,
                        "-vn",  # sin video
                        "-acodec", "libmp3lame",
                        "-ab", "192k",
                        "-f", "mp3",
                        "pipe:1"
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )

                # Leemos la salida binaria directamente
                audio_data = process.stdout.read()
                buffer.write(audio_data)
                process.stdout.close()
                process.wait()

            buffer.seek(0)
            title = info.get("title", "audio")
            filename = f"{title[:80]}.mp3"

            # Discord tiene límite de 8 MB en archivos para bots sin Nitro
            size_mb = len(buffer.getvalue()) / (1024 * 1024)
            if size_mb > 8:
                await interaction.followup.send(
                    f"⚠️ El archivo pesa {size_mb:.2f} MB (máximo 8 MB). No puedo enviarlo directamente."
                )
                return

            await interaction.followup.send(
                content=f"🎧 **{title}**",
                file=discord.File(buffer, filename=filename)
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`")
