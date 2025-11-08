import discord
from discord.ext import commands
from discord import app_commands
from utils.data import load_data, PATH_USERS, save_data

class Example(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="jugar", description="Debes registrarte para jugar")

    async def jugar(interaction: discord.Interaction):
        # Responder a la interacción
        user_id = str(interaction.user.id)
        data_users = await load_data(PATH_USERS)
        if user_id not in data_users:
            data_users[user_id] = {
                "dinero": 0,
                "experiencia": 0,
                "date_job": None,
                "job": None,
                "salud": 100,
                "date_disease": None,
                "disease": None,
            }
            await save_data(data_users, PATH_USERS)
            await interaction.response.send_message("¡Te has registrado en el juego! Usa /trabajos")
        else:
            await interaction.response.send_message("Ya estás registrado en el juego.")
        

async def setup(bot):
    await bot.add_cog(Example(bot))