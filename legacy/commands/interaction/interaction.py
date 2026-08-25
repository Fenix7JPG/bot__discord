import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random

class Interaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    # --- Inicializar y cerrar sesión HTTP ---
    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        print("✅ [Interaction] Sesión HTTP creada")

    async def cog_unload(self):
        if self.session:
            await self.session.close()
            print("❌ [Interaction] Sesión HTTP cerrada")

    # --- Funciones para obtener GIFs ---
    async def get_pat_gif(self):
        if not self.session:
            return None
        try:
            async with self.session.get("https://nekos.best/api/v2/pat", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "results" in data and len(data["results"]) > 0:
                        result = data["results"][0]
                        return {
                            "url": result.get("url"),
                            "anime_name": result.get("anime_name")
                        }
        except Exception:
            return None

    async def get_punch_gif(self):
        if not self.session:
            return None
        try:
            async with self.session.get("https://nekos.best/api/v2/punch", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "results" in data and len(data["results"]) > 0:
                        result = data["results"][0]
                        return {
                            "url": result.get("url"),
                            "anime_name": result.get("anime_name")
                        }
        except Exception:
            return None

    # --- Grupo principal /interact ---
    interaction_group = app_commands.Group(
        name="interact",
        description="Interactúa con alguien"
    )

    # --- Comando /interact pat ---
    @interaction_group.command(name="pat", description="Da un pat a alguien")
    @app_commands.describe(user="Da una caricia a este usuario")
    async def pat_command(self, interaction: discord.Interaction, user: discord.Member):
        gif_data = await self.get_pat_gif()
        if not gif_data or not gif_data.get("url"):
            await interaction.response.send_message("No pude conseguir un GIF 😢")
            return

        if user.id == interaction.user.id:
            title = f"{interaction.user.display_name} se acaricia a sí mismo 😳"
            description = None
        else:
            title = f"¡{interaction.user.display_name} acaricia a {user.display_name}!"
            caricias = random.randint(5, 20)
            description = f"{user.display_name} ha recibido **{caricias}** caricias."

        embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
        embed.set_image(url=gif_data["url"])
        embed.set_footer(text=f"Anime: {gif_data['anime_name']}")
        await interaction.response.send_message(embed=embed)

    # --- Comando /interact punch ---
    @interaction_group.command(name="punch", description="Da un golpe a alguien")
    @app_commands.describe(user="Golpea a este usuario")
    async def punch_command(self, interaction: discord.Interaction, user: discord.Member):
        gif_data = await self.get_punch_gif()
        if not gif_data or not gif_data.get("url"):
            await interaction.response.send_message("No pude conseguir un GIF 😢")
            return

        if user.id == interaction.user.id:
            title = f"{interaction.user.display_name} se golpea a sí mismo 😳"
            description = None
        else:
            title = f"💥 {interaction.user.display_name} golpea a {user.display_name}!"
            golpes = random.randint(1, 10) # Despues implemntar en la bd
            description = f"{user.display_name} ha recibido **{golpes}** golpes."

        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        embed.set_image(url=gif_data["url"])
        embed.set_footer(text=f"Anime: {gif_data['anime_name']}")
        await interaction.response.send_message(embed=embed)

# --- Setup del cog ---
async def setup(bot):
    await bot.add_cog(Interaction(bot))