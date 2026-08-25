"""Cog /ytmp3: descarga audio de YouTube y lo envia como MP3."""

import os
import shutil
import subprocess
import tempfile
from io import BytesIO

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands


class YtMp3(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ytmp3", description="Descarga audio de YouTube como MP3.")
    @app_commands.describe(query="Nombre o URL del video de YouTube")
    async def ytmp3(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"

        # Cookies opcionales (Render las monta como Secret File)
        ruta_cookies = None
        ruta_temporal = None
        origen_cookies = os.getenv("YT_COOKIES_FILE", "/etc/secrets/youtube_cookies.txt")
        try:
            if origen_cookies and os.path.exists(origen_cookies):
                fd, ruta_temporal = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
                os.close(fd)
                shutil.copyfile(origen_cookies, ruta_temporal)
                ruta_cookies = ruta_temporal

            opciones = {
                "format": "bestaudio/best",
                "quiet": True,
                "noplaylist": True,
            }
            if ruta_cookies:
                opciones["cookiefile"] = ruta_cookies

            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(query, download=False)

            url_audio = info.get("url")
            if not url_audio:
                formatos = [f for f in (info.get("formats") or []) if f.get("acodec", "none") != "none"]
                if not formatos:
                    await interaction.followup.send("No encontre audio para ese video.")
                    return
                mejor = max(formatos, key=lambda f: f.get("abr") or f.get("tbr") or 0)
                url_audio = mejor.get("url")

            # Convertir el stream a MP3 en memoria con ffmpeg
            proceso = subprocess.Popen(
                [
                    ffmpeg_path, "-i", url_audio,
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-ab", "192k",
                    "-f", "mp3",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            datos_audio = proceso.stdout.read()
            proceso.stdout.close()
            proceso.wait()

            buffer = BytesIO(datos_audio)
            titulo = info.get("title", "audio")
            nombre_archivo = titulo[:80] + ".mp3"

            peso_mb = len(buffer.getvalue()) / (1024 * 1024)
            if peso_mb > 8:
                await interaction.followup.send(
                    "El archivo pesa " + str(round(peso_mb, 2)) + " MB (maximo 8 MB). No puedo enviarlo."
                )
                return

            buffer.seek(0)
            await interaction.followup.send(content=titulo, file=discord.File(buffer, filename=nombre_archivo))

        except Exception as e:
            await interaction.followup.send("Error: " + str(e))
        finally:
            if ruta_temporal and os.path.exists(ruta_temporal):
                try:
                    os.remove(ruta_temporal)
                except Exception:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(YtMp3(bot))
