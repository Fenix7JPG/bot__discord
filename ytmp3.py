# commands/ytmp3.py
import os
import discord
from discord import app_commands
import yt_dlp
from io import BytesIO
import subprocess
import tempfile
import shutil

def ytmp3(tree: app_commands.CommandTree):

    @tree.command(name="ytmp3", description="Descarga música de YouTube y la envía como MP3 🎵")
    @app_commands.describe(query="Nombre o URL del video de YouTube")
    async def ytmp3(interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        # Usar variable de entorno si está definida, sino el path por defecto (montado como Secret File)
        cookiefile_env = os.getenv("YT_COOKIES_FILE", "/etc/secrets/youtube_cookies.txt")
        if not cookiefile_env or not os.path.exists(cookiefile_env):
            await interaction.followup.send(
                "⚠️ No está configurado el archivo de cookies. "
                "En Render añade un Secret File con el contenido de cookies.txt y configura "
                "la variable de entorno `YT_COOKIES_FILE=/etc/secrets/youtube_cookies.txt`."
            )
            return

        # Copiamos a un fichero temporal en un directorio escribible para evitar errores de solo-lectura
        tmp_cookie_path = None
        try:
            # crea un archivo temporal en /tmp (o en el tmp del sistema)
            fd, tmp_cookie_path = tempfile.mkstemp(prefix="youtube_cookies_", suffix=".txt")
            os.close(fd)  # cerramos descriptor, usaremos shutil.copyfile
            shutil.copyfile(cookiefile_env, tmp_cookie_path)
        except Exception as e:
            await interaction.followup.send(f"❌ Error al preparar el archivo de cookies: `{e}`")
            # limpiar si quedó algo
            try:
                if tmp_cookie_path and os.path.exists(tmp_cookie_path):
                    os.remove(tmp_cookie_path)
            except Exception:
                pass
            return

        # Configurar yt-dlp con cookiefile (apuntando a la copia temporal escribible)
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            # si no tienes aria2c instalado en Render, quita el downloader externo

            "cookiefile": tmp_cookie_path,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        try:
            buffer = BytesIO()

            def progress_hook(d):
                if d.get("status") == "finished":
                    print("✅ Descarga completada, convirtiendo a MP3...")

            ydl_opts["progress_hooks"] = [progress_hook]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)

                # Seleccionar mejor formato de audio
                url = None
                formats = info.get("formats") or []
                audio_formats = [f for f in formats if f.get("acodec") and f.get("acodec") != "none"]
                if audio_formats:
                    def score(f):
                        return f.get("abr") or f.get("tbr") or 0
                    best = max(audio_formats, key=score)
                    url = best.get("url")
                else:
                    url = info.get("url")

                if not url:
                    raise RuntimeError("No pude obtener una URL de audio válida para ese vídeo.")

                # Convertir stream a mp3 con ffmpeg y leer en memoria
                process = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-i", url,
                        "-vn",
                        "-acodec", "libmp3lame",
                        "-ab", "192k",
                        "-f", "mp3",
                        "pipe:1"
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )

                audio_data = process.stdout.read()
                buffer.write(audio_data)
                process.stdout.close()
                process.wait()

            buffer.seek(0)
            title = info.get("title", "audio")
            filename = f"{title[:80]}.mp3"

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
        finally:
            # borrar el archivo temporal de cookies si existe
            try:
                if tmp_cookie_path and os.path.exists(tmp_cookie_path):
                    os.remove(tmp_cookie_path)
            except Exception:
                pass
