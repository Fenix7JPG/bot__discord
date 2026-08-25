"""Comandos de administracion y diagnostico."""

import asyncio
import shutil

import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from database.database import db


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, ctx, scope: str = None):
        """Sincroniza los slash commands. !sync global o !sync (este server)."""
        if scope == "global":
            await ctx.send("Sincronizando globalmente...")
            await self.bot.tree.sync()
            await ctx.send("Sincronizacion global completa.")
        else:
            await ctx.send("Sincronizando en este servidor...")
            self.bot.tree.copy_global_to(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send("Sincronizado en este servidor.")

    @commands.command(name="getpaths")
    @commands.is_owner()
    async def getpaths(self, ctx):
        """Muestra la configuracion de datos del bot."""
        await ctx.send("Trabajos: tabla 'trabajos' en la base de datos")
        await ctx.send("Enfermedades: tabla 'enfermedades' en la base de datos")
        await ctx.send("Base de datos local (ruta): " + settings.db_path)
        await ctx.send("Modo de BD: " + db_mode_actual())

    @app_commands.command(name="checkffmpeg", description="Revisa que FFmpeg este disponible.")
    async def checkffmpeg(self, interaction: discord.Interaction):
        await interaction.response.defer()

        ruta_ffmpeg = shutil.which("ffmpeg")
        if ruta_ffmpeg is None:
            await interaction.followup.send(
                "FFmpeg no se encontro en el PATH del sistema. "
                "En Render debe instalarse en render-build.sh."
            )
            return

        try:
            proceso = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            salida, _error = await asyncio.wait_for(proceso.communicate(), timeout=10)
        except FileNotFoundError:
            await interaction.followup.send("FFmpeg no esta instalado en este sistema.")
            return
        except asyncio.TimeoutError:
            proceso.kill()
            await interaction.followup.send("FFmpeg no respondio en 10 segundos.")
            return

        primera_linea = salida.decode(errors="ignore").splitlines()[0]
        await interaction.followup.send(
            "FFmpeg OK en `" + ruta_ffmpeg + "`\n`" + primera_linea + "`"
        )


def db_mode_actual() -> str:
    return db.mode


async def setup(bot):
    await bot.add_cog(Admin(bot))
