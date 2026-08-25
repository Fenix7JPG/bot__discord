# comando para ver los path

from utils.cookies_path import COOKIES_PATH
from utils.ffmpeg_path import FFMPEG_PATH
from utils.data import PATH_USERS, PATH_TRABAJOS
import discord
from discord.ext import commands

class GetPath(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Este comando solo lo puede usar el dueño del bot
    @commands.command(name="getpath")
    #@commands.is_owner()
    async def getpath(self, ctx):
        await ctx.send(f"🍪 Path de cookies: {COOKIES_PATH}")
        await ctx.send(f"🎥 Path de FFmpeg: {FFMPEG_PATH}")
        await ctx.send(f"👤 Path de usuarios: {PATH_USERS}")
        await ctx.send(f"💼 Path de trabajos: {PATH_TRABAJOS}")
async def setup(bot):
    await bot.add_cog(GetPath(bot))
