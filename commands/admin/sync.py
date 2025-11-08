# cogs/admin.py
import discord
from discord.ext import commands

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Este comando solo lo puede usar el dueño del bot
    @commands.command(name="sync", hidden=True) # hidden=True para que no aparezca en !help
    @commands.is_owner()
    async def sync(self, ctx):
        """Sincroniza los comandos de barra globalmente."""
        await ctx.send("Sincronizando comandos de barra...")
        await self.bot.tree.sync()
        await ctx.send("✅ Comandos sincronizados.")

async def setup(bot):
    await bot.add_cog(Sync(bot))