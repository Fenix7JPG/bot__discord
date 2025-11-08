import discord
from discord.ext import commands
from discord import app_commands
import random
class Dice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="d6", description="Lanza un dado de 6 caras 🎲")
    async def d6(self,interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 Has lanzado un **d6** → **{result}**")

    @app_commands.command(name="d10", description="Lanza un dado de 10 caras 🎲")
    async def d10(self,interaction: discord.Interaction):
        result = random.randint(1, 10)
        await interaction.response.send_message(f"🎲 Has lanzado un **d10** → **{result}**")

    @app_commands.command(name="d20", description="Lanza un dado de 20 caras 🎲")
    async def d20(self,interaction: discord.Interaction):
        result = random.randint(1, 20)
        await interaction.response.send_message(f"🎲 Has lanzado un **d20** → **{result}**")



async def setup(bot):
    await bot.add_cog(Dice(bot))