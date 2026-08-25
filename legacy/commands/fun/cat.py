# cogs/fun.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

class Cat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # La sesión se creará en cog_load, no aquí.
        self.session: aiohttp.ClientSession | None = None

    # --- MÉTODO ESPECIAL: Se ejecuta cuando el Cog se carga ---
    async def cog_load(self):
        """Crea la sesión de red cuando el Cog se añade al bot."""
        self.session = aiohttp.ClientSession()
        print("✅ [Fun Cog] Sesión de aiohttp creada.")

    # --- MÉTODO ESPECIAL: Se ejecuta cuando el Cog se descarga ---
    async def cog_unload(self):
        """Cierra la sesión de red para liberar recursos."""
        if self.session:
            await self.session.close()
            print("❌ [Fun Cog] Sesión de aiohttp cerrada.")

    @app_commands.command(name="cat", description="Envía una imagen de gato al azar 🐱")
    async def cat(self, interaction: discord.Interaction):
        """Envía una imagen de un gatito."""
        # Verificamos que la sesión esté disponible (por si acaso)
        if not self.session:
            await interaction.response.send_message("Error interno: la sesión de red no está disponible.", ephemeral=True)
            return

        await interaction.response.defer()  # Evita timeouts mientras buscamos la imagen

        # Usamos self.session, que fue creada en cog_load
        urls_to_try = [
            ("https://api.thecatapi.com/v1/images/search", "json", lambda j: j[0]["url"]),
            ("https://aws.random.cat/meow", "json", lambda j: j["file"]),
            ("https://cataas.com/cat?json=true", "json", lambda j: "https://cataas.com" + j["url"]),
        ]

        image_url = None
        for url, rtype, extractor in urls_to_try:
            try:
                async with self.session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        if rtype == "json":
                            j = await resp.json()
                            image_url = extractor(j)
                            if image_url:
                                break
            except Exception:
                # Si una API falla, continuamos con la siguiente
                continue

        if not image_url:
            await interaction.followup.send("❌ No pude obtener una imagen de gato ahora. Intenta de nuevo más tarde.")
            return

        embed = discord.Embed(title="", color=0xF5A9B8)
        embed.set_image(url=image_url)
        embed.set_footer(text="Imagen de gato 🐱")

        await interaction.followup.send(embed=embed)

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Cat(bot))