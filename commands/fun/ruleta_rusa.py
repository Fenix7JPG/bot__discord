# cogs/russian_roulette.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# --- CLASES DEL JUEGO (Sin cambios, ahora dentro del fichero del Cog) ---

class RussianRouletteView(discord.ui.View):
    def __init__(self, game: "RussianRouletteGame"):
        super().__init__(timeout=None) # timeout=None para que no se deshabilite sola
        self.game = game

    @discord.ui.button(label="Unirse", style=discord.ButtonStyle.success, custom_id="rr_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        added = await self.game.add_player(interaction.user)
        if added:
            await interaction.response.edit_message(content=self.game.join_message_text(), view=self)
        else:
            await interaction.response.send_message("Ya estás en la lista o el juego ya empezó.", ephemeral=True)

    @discord.ui.button(label="Abandonar", style=discord.ButtonStyle.danger, custom_id="rr_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        removed = await self.game.remove_player(interaction.user)
        if removed:
            await interaction.response.edit_message(content=self.game.join_message_text(), view=self)
        else:
            await interaction.response.send_message("No estabas en la lista o el juego ya empezó.", ephemeral=True)

    @discord.ui.button(label="Empezar", style=discord.ButtonStyle.primary, custom_id="rr_start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.started:
            await interaction.response.send_message("El juego ya empezó.", ephemeral=True)
            return
        if len(self.game.players) < 2:
            await interaction.response.send_message("Se necesitan al menos 2 jugadores para empezar.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=self.game.join_message_text(starting=True), view=self)
        asyncio.create_task(self.game.run_game())

class RussianRouletteGame:
    def __init__(self, channel: discord.TextChannel, initiator: discord.Member):
        self.channel = channel
        self.players: list[discord.Member] = []
        self.started = False
        self.chambers = [False]*6
        self.current_chamber_index = 0
        self.current_player_idx = 0
        self.reset_event = asyncio.Event()
        self.countdown_active = False
        self.initiator = initiator
        self.view_message: discord.Message | None = None

    def join_message_text(self, starting: bool = False) -> str:
        lines = ["**— RULETA RUSA —**", "Pulsa **Unirse** para entrar o **Abandonar** para salir."]
        if not self.players:
            lines.append("\n**Jugadores (0):** (aún nadie)")
        else:
            names = ", ".join(p.display_name for p in self.players)
            lines.append(f"\n**Jugadores ({len(self.players)}):** {names}")
        if starting:
            lines.append("\n> El juego ha comenzado. ¡Suerte!")
        return "\n".join(lines)

    async def add_player(self, user: discord.User) -> bool:
        if self.started or any(p.id == user.id for p in self.players):
            return False
        member = user if isinstance(user, discord.Member) else await self.channel.guild.fetch_member(user.id)
        self.players.append(member)
        return True

    async def remove_player(self, user: discord.User) -> bool:
        if self.started:
            return False
        for p in self.players:
            if p.id == user.id:
                self.players.remove(p)
                return True
        return False

    def _place_bullet(self):
        self.chambers = [False]*6
        self.chambers[random.randrange(6)] = True
        self.current_chamber_index = 0

    async def run_game(self):
        self.started = True
        if len(self.players) < 2:
            await self.channel.send("No hay suficientes jugadores. Juego cancelado.")
            self.cleanup()
            return

        await self.channel.send("Orden de juego:\n" + "\n".join(f"{i+1}. {p.mention}" for i, p in enumerate(self.players)))
        self._place_bullet()

        while len(self.players) > 1:
            current_player = self.players[self.current_player_idx % len(self.players)]
            warn_msg = await self.channel.send(f"🔫 **Turno de {current_player.mention}** — se prepara para disparar... (5s)")
            await self._wait_with_resets()

            chamber_has_bullet = self.chambers[self.current_chamber_index]
            if chamber_has_bullet:
                await self.channel.send(f"💥 **{current_player.mention}** se ha disparado. Ha muerto.")
                self.players = [p for p in self.players if p.id != current_player.id]
                if len(self.players) <= 1:
                    if self.players:
                        await self.channel.send(f"🏆 **{self.players[0].mention}** es el último en pie. ¡Ganador!")
                    else:
                        await self.channel.send("No quedan jugadores. Fin del juego.")
                    self.cleanup()
                    return
                self._place_bullet()
                if self.current_player_idx >= len(self.players):
                    self.current_player_idx = 0
                await self.channel.send("🔄 Se recarga el arma y la partida continúa.")
            else:
                await self.channel.send(f"🔒 **{current_player.mention}** ha disparado y *vive* (click).")
                self.current_chamber_index = (self.current_chamber_index + 1) % 6
                self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

        if len(self.players) == 1:
            await self.channel.send(f"🏆 **{self.players[0].mention}** es el último en pie. ¡Ganador!")
        else:
            await self.channel.send("Juego terminado.")
        self.cleanup()

    async def _wait_with_resets(self):
        while True:
            self.reset_event.clear()
            try:
                await asyncio.wait_for(self.reset_event.wait(), timeout=5.0)
                continue
            except asyncio.TimeoutError:
                break

    def reset_countdown(self):
        try:
            self.reset_event.set()
        except Exception:
            pass

    def cleanup(self):
        try:
            del self.bot.games_by_channel[self.channel.id]
        except (KeyError, AttributeError):
            pass


####################################################################################
# --- EL COG PRINCIPAL ---

class RussianRoulette(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # CAMBIO CLAVE: Guardamos los juegos en la instancia del bot, no en una variable global.
        if not hasattr(bot, 'games_by_channel'):
            bot.games_by_channel = {}

    # --- COMANDO DE BARRA ---
    @app_commands.command(name="ruleta-rusa", description="Inicia una partida de ruleta rusa.")
    async def ruleta_rusa(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Este comando solo puede usarse en un canal de texto.", ephemeral=True)
            return

        # Usamos self.bot.games_by_channel
        if channel.id in self.bot.games_by_channel:
            await interaction.response.send_message("Ya hay una ruleta activa en este canal.", ephemeral=True)
            return

        game = RussianRouletteGame(channel=channel, initiator=interaction.user)
        # Le pasamos la instancia del bot al juego para que pueda acceder a games_by_channel en cleanup
        game.bot = self.bot
        view = RussianRouletteView(game)
        
        msg = await channel.send(content=game.join_message_text(), view=view)
        game.view_message = msg
        
        self.bot.games_by_channel[channel.id] = game
        await interaction.response.send_message("Se ha creado la ruleta. ¡Únete con los botones en el mensaje!", ephemeral=True)

    # --- EVENT LISTENER (La forma correcta de manejar eventos en un Cog) ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar mensajes de bots y DMs
        if message.author.bot or not message.guild:
            return

        # Comprobar si hay un juego en el canal actual
        game = self.bot.games_by_channel.get(message.channel.id)
        if game and not game.started:
            game.reset_countdown()

# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(RussianRoulette(bot))