import discord
from discord.ext import commands
from discord import app_commands

class Example2(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="example2", description="ejemplo")
    async def ping(self, ctx: commands.Context):
        await ctx.send(f"Mensaje de prueba2")

async def setup(bot):
    await bot.add_cog(Example2(bot))