
import discord
import random
from discord.ext import commands
from discord import app_commands

from utils.data import load_data, PATH_USERS, save_data



def create_deck() -> list:
    suits = ["♠", "♥", "♦", "♣"]
    ranks = ["A"] + [str(n) for n in range(2, 11)] + ["J", "Q", "K"]
    return [f"{r}{s}" for s in suits for r in ranks]

def card_value(card: str) -> int:
    rank = card[:-1]
    if rank in ("J", "Q", "K"):
        return 10
    return 11 if rank == "A" else int(rank)

def hand_value(cards: list) -> tuple:
    total = sum(card_value(card) for card in cards)
    aces = sum(1 for card in cards if card.startswith('A'))
    
    # Ajustar el valor de los Ases de 11 a 1 si nos pasamos de 21
    while total > 21 and aces:
        total -= 10
        aces -= 1
        
    is_soft = any(card.startswith('A') for card in cards) and total <= 21
    return total, is_soft

def card_display(card: str) -> str:
    return f"`{card}`"



class BlackJack(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- CAMBIO CLAVE: Usa @app_commands.command en lugar de @commands.hybrid_command ---
    @app_commands.command(name="blackjack", description="Juega una mano de blackjack.")
    @app_commands.describe(
        apuesta="Elige una cantidad para apostar."
    )
    async def blackjack(self, interaction: discord.Interaction, apuesta: int):
        # --- Ya no necesitamos comprobar si es Context o Interaction. Siempre será Interaction. ---
        
        try:
            if apuesta <= 0:
                return await interaction.response.send_message("🔸 La apuesta debe ser un número entero mayor que 0.", ephemeral=True)

            user_id = str(interaction.user.id) # <-- Ahora podemos usar interaction.user directamente
            data_users = await load_data(PATH_USERS)

            if user_id not in data_users:
                return await interaction.response.send_message("❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True)
            
            user_money = int(data_users[user_id].get("dinero", 0))
            if user_money < apuesta:
                return await interaction.response.send_message("❌ No tienes suficiente dinero para esa apuesta.", ephemeral=True)

            deck = create_deck()
            random.shuffle(deck)
            player_hand = [deck.pop(), deck.pop()]
            dealer_hand = [deck.pop(), deck.pop()]

            data_users[user_id]['dinero'] = user_money - apuesta
            await save_data(data_users, PATH_USERS)

            # Pasamos interaction.user a la vista
            view = BlackjackView(self.bot, interaction.user, player_hand, dealer_hand, deck, apuesta)
            await interaction.response.send_message(embed=view.build_embed(), view=view)

        except Exception as e:
            print(f"Error en el comando blackjack: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Ocurrió un error: `{type(e).__name__}: {e}`", ephemeral=True)
            else:
                await interaction.followup.send(f"Ocurrió un error: `{type(e).__name__}: {e}`", ephemeral=True)
class BlackjackView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member, player_hand: list, dealer_hand: list, deck: list, bet: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.bet = bet
        self.ended = False

    def build_embed(self, reveal_dealer: bool = False, note: str = "") -> discord.Embed:
        """Construye el embed del estado del juego."""
        dealer_val, _ = hand_value(self.dealer_hand)
        if reveal_dealer:
            dealer_display = " ".join(map(card_display, self.dealer_hand))
            dealer_line = f"{dealer_display} — **{dealer_val}**"
        else:
            dealer_display = f"{card_display(self.dealer_hand[0])} 🂠"
            dealer_line = f"{dealer_display} — visible: **{card_value(self.dealer_hand[0])}**"

        player_val, _ = hand_value(self.player_hand)
        player_display = " ".join(map(card_display, self.player_hand))

        embed = discord.Embed(
            title=f"🃏 Blackjack — Apuesta ${self.bet}",
            description=note or "Elige tu acción.",
            color=0x2F3136
        )
        embed.add_field(name="Dealer", value=dealer_line, inline=False)
        embed.add_field(name=f"{self.author.display_name}", value=f"{player_display} — **{player_val}**", inline=False)
        return embed

    async def _update_message(self, interaction: discord.Interaction, note: str = "", disable_all: bool = False):
        """Función auxiliar para editar el mensaje y desactivar botones."""
        if disable_all:
            for child in self.children:
                child.disabled = True
            self.stop()
        
        embed = self.build_embed(reveal_dealer=self.ended, note=note)
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Asegura que solo el autor de la partida pueda interactuar."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("No puedes usar estos botones.", ephemeral=True)
            return False
        return True

    # --- BOTONES DE ACCIÓN ---
    # NOTA: La firma correcta es async def callback(self, interaction)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self.deck.pop())
        player_val, _ = hand_value(self.player_hand)

        if player_val > 21:
            self.ended = True
            await self.end_game(interaction, result="bust")
        else:
            # Desactivar "Double Down" después del primer hit
            self.children[2].disabled = True 
            await self._update_message(interaction, note=f"Has pedido carta. Tu total: {player_val}.")

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve_dealer(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, custom_id="bj_double")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Lógica de doble apuesta (simplificada para el ejemplo)
        # Aquí deberías volver a comprobar si el usuario tiene suficiente dinero
        self.player_hand.append(self.deck.pop())
        player_val, _ = hand_value(self.player_hand)
        self.bet *= 2

        if player_val > 21:
            self.ended = True
            await self.end_game(interaction, result="bust")
        else:
            await self.resolve_dealer(interaction)

    async def resolve_dealer(self, interaction: discord.Interaction):
        """El dealer juega su mano."""
        dealer_val, _ = hand_value(self.dealer_hand)
        while dealer_val < 17:
            self.dealer_hand.append(self.deck.pop())
            dealer_val, _ = hand_value(self.dealer_hand)
        
        player_val, _ = hand_value(self.player_hand)
        
        if dealer_val > 21: self.ended = True; await self.end_game(interaction, result="dealer_bust")
        elif player_val > dealer_val: self.ended = True; await self.end_game(interaction, result="win")
        elif player_val < dealer_val: self.ended = True; await self.end_game(interaction, result="lose")
        else: self.ended = True; await self.end_game(interaction, result="tie")

    async def end_game(self, interaction: discord.Interaction, result: str):
        """Finaliza el juego, calcula pagos y guarda los datos."""
        user_id = str(self.author.id)
        data_users = await load_data(PATH_USERS)
        current_money = data_users[user_id].get('dinero', 0)
        
        note = ""
        if result == "bust":
            note = f"💥 Te pasaste de 21. Pierdes ${self.bet}."
        elif result == "dealer_bust":
            note = f"🏆 El dealer se pasó. Ganas ${self.bet}."
            data_users[user_id]['dinero'] = current_money + (self.bet * 2)
        elif result == "win":
            note = f"🏆 Ganaste con {hand_value(self.player_hand)[0]} vs {hand_value(self.dealer_hand)[0]}. Ganas ${self.bet}."
            data_users[user_id]['dinero'] = current_money + (self.bet * 2)
        elif result == "lose":
            note = f"❌ Perdiste con {hand_value(self.player_hand)[0]} vs {hand_value(self.dealer_hand)[0]}. Pierdes ${self.bet}."
        elif result == "tie":
            note = f"🤝 Empate. Recuperas tu apuesta de ${self.bet}."
            data_users[user_id]['dinero'] = current_money + self.bet

        await save_data(data_users, PATH_USERS)
        await self._update_message(interaction, note=note, disable_all=True)

    async def on_timeout(self):
        """Desactiva los botones si el tiempo se agota."""
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(content="⏲️ Tiempo agotado.", view=self)
        except discord.NotFound:
            pass


# --- FUNCIÓN DE CONFIGURACIÓN DEL COG ---
async def setup(bot: commands.Bot):
    await bot.add_cog(BlackJack(bot))