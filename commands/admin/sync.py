# cogs/admin.py
import discord
from discord.ext import commands

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Este comando solo lo puede usar el dueño del bot
    @commands.command(name="sync", hidden=True)
    @commands.is_owner()
    async def sync(self, ctx):
        await ctx.send("Sincronizando en este servidor...")
    
        guild = ctx.guild
        self.bot.tree.copy_global_to(guild=guild)
        await self.bot.tree.sync(guild=guild)
    
        await ctx.send("✅ Comandos sincronizados en este servidor.")
async def setup(bot):
    await bot.add_cog(Sync(bot))
