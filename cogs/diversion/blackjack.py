"""Cog /blackjack: mano de blackjack contra el dealer."""

import random

import discord
from discord import app_commands
from discord.ext import commands

from database import jugadores_repo


def crear_mazo() -> list:
    palos = ["♠", "♥", "♦", "♣"]
    rangos = ["A"] + [str(n) for n in range(2, 11)] + ["J", "Q", "K"]
    mazo = []
    for palo in palos:
        for rango in rangos:
            mazo.append(rango + palo)
    random.shuffle(mazo)
    return mazo


def valor_carta(carta: str) -> int:
    rango = carta[:-1]
    if rango in ("J", "Q", "K"):
        return 10
    if rango == "A":
        return 11
    return int(rango)


def valor_mano(cartas: list) -> int:
    """Suma de la mano bajando los Ases de 11 a 1 si hace falta."""
    total = sum(valor_carta(carta) for carta in cartas)
    ases = sum(1 for carta in cartas if carta.startswith("A"))
    while total > 21 and ases:
        total -= 10
        ases -= 1
    return total


def mostrar_carta(carta: str) -> str:
    return "`" + carta + "`"


class VistaBlackjack(discord.ui.View):
    """Botones Pedir / Plantarse / Doblar de la mano en curso."""

    def __init__(self, autor_id: int, mano_jugador: list, mano_dealer: list, mazo: list, apuesta: int):
        super().__init__(timeout=180)
        self.autor_id = autor_id
        self.mano_jugador = mano_jugador
        self.mano_dealer = mano_dealer
        self.mazo = mazo
        self.apuesta = apuesta
        self.terminado = False
        self.message = None

    def construir_embed(self, revelar_dealer: bool = False, nota: str = "") -> discord.Embed:
        """Arma el embed con el estado de la partida."""
        if revelar_dealer:
            cartas_dealer = " ".join(mostrar_carta(c) for c in self.mano_dealer)
            linea_dealer = cartas_dealer + " - **" + str(valor_mano(self.mano_dealer)) + "**"
        else:
            linea_dealer = (
                mostrar_carta(self.mano_dealer[0])
                + " 🂠 - visible: **"
                + str(valor_carta(self.mano_dealer[0]))
                + "**"
            )
        cartas_jugador = " ".join(mostrar_carta(c) for c in self.mano_jugador)
        embed = discord.Embed(
            title="🃏 Blackjack - Apuesta $" + str(self.apuesta),
            description=nota or "Elige tu acción.",
            color=0x2F3136,
        )
        embed.add_field(name="Dealer", value=linea_dealer, inline=False)
        embed.add_field(
            name="Tu mano",
            value=cartas_jugador + " - **" + str(valor_mano(self.mano_jugador)) + "**",
            inline=False,
        )
        return embed

    def _deshabilitar_todo(self):
        for child in self.children:
            child.disabled = True
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Solo el autor de la partida puede pulsar los botones."""
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("No puedes usar estos botones.", ephemeral=True)
            return False
        return True

    def _boton_doblar(self):
        for child in self.children:
            if getattr(child, "label", "") == "Doblar":
                return child
        return None

    async def terminar(self, interaction: discord.Interaction, resultado: str):
        """Cobra o paga segun el resultado y cierra la vista."""
        self.terminado = True
        jugador = jugadores_repo.get_jugador(self.autor_id)
        dinero_actual = int((jugador or {}).get("dinero", 0) or 0)
        puntos_jugador = valor_mano(self.mano_jugador)
        puntos_dealer = valor_mano(self.mano_dealer)

        # La apuesta ya estaba descontada; aqui solo se devuelven los premios.
        if resultado == "bust":
            nota = "💥 Te pasaste de 21. Pierdes $" + str(self.apuesta) + "."
        elif resultado == "dealer_bust":
            jugadores_repo.actualizar_campo(self.autor_id, "dinero", dinero_actual + self.apuesta * 2)
            nota = "🏆 El dealer se pasó con " + str(puntos_dealer) + ". Ganas $" + str(self.apuesta) + "."
        elif resultado == "win":
            jugadores_repo.actualizar_campo(self.autor_id, "dinero", dinero_actual + self.apuesta * 2)
            nota = (
                "🏆 Ganaste "
                + str(puntos_jugador)
                + " vs "
                + str(puntos_dealer)
                + ". Ganas $"
                + str(self.apuesta)
                + "."
            )
        elif resultado == "lose":
            nota = (
                "❌ Perdiste "
                + str(puntos_jugador)
                + " vs "
                + str(puntos_dealer)
                + ". Pierdes $"
                + str(self.apuesta)
                + "."
            )
        else:
            jugadores_repo.actualizar_campo(self.autor_id, "dinero", dinero_actual + self.apuesta)
            nota = (
                "🤝 Empate en "
                + str(puntos_jugador)
                + ". Recuperas tu apuesta de $"
                + str(self.apuesta)
                + "."
            )

        self._deshabilitar_todo()
        await interaction.response.edit_message(
            content=None, embed=self.construir_embed(revelar_dealer=True, nota=nota), view=self
        )

    async def resolver_dealer(self, interaction: discord.Interaction):
        """El dealer roba hasta llegar a 17 y se compara la mano."""
        while valor_mano(self.mano_dealer) < 17:
            self.mano_dealer.append(self.mazo.pop(0))
        jugador_valor = valor_mano(self.mano_jugador)
        dealer_valor = valor_mano(self.mano_dealer)

        if dealer_valor > 21:
            await self.terminar(interaction, "dealer_bust")
        elif jugador_valor > dealer_valor:
            await self.terminar(interaction, "win")
        elif jugador_valor < dealer_valor:
            await self.terminar(interaction, "lose")
        else:
            await self.terminar(interaction, "tie")

    @discord.ui.button(label="Pedir", style=discord.ButtonStyle.primary)
    async def pedir(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        self.mano_jugador.append(self.mazo.pop(0))
        total = valor_mano(self.mano_jugador)
        if total > 21:
            await self.terminar(interaction_btn, "bust")
            return
        doblar_btn = self._boton_doblar()
        if doblar_btn is not None:
            doblar_btn.disabled = True  # tras pedir carta ya no se puede doblar
        await interaction_btn.response.edit_message(
            embed=self.construir_embed(nota="Has pedido carta. Tu total: " + str(total) + "."), view=self
        )

    @discord.ui.button(label="Plantarse", style=discord.ButtonStyle.secondary)
    async def plantarse(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        await self.resolver_dealer(interaction_btn)

    @discord.ui.button(label="Doblar", style=discord.ButtonStyle.success)
    async def doblar(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        # Se validan los fondos reales antes de duplicar la apuesta.
        jugador = jugadores_repo.get_jugador(self.autor_id)
        dinero = int((jugador or {}).get("dinero", 0) or 0)
        if dinero < self.apuesta:
            await interaction_btn.response.send_message(
                "No tienes suficiente dinero para doblar la apuesta ($" + str(self.apuesta) + ").",
                ephemeral=True,
            )
            return

        jugadores_repo.actualizar_campo(self.autor_id, "dinero", dinero - self.apuesta)
        self.apuesta *= 2
        self.mano_jugador.append(self.mazo.pop(0))
        total = valor_mano(self.mano_jugador)
        if total > 21:
            await self.terminar(interaction_btn, "bust")
        else:
            await self.resolver_dealer(interaction_btn)

    async def on_timeout(self):
        """Al agotarse el tiempo se desactivan los botones del mensaje."""
        for child in self.children:
            child.disabled = True
        try:
            if self.message is not None:
                await self.message.edit(content="⏲️ Tiempo agotado.", view=self)
        except discord.HTTPException:
            pass


class BlackJack(commands.Cog):
    """Juego de blackjack sobre el perfil guardado en base de datos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Juega una mano de blackjack.")
    @app_commands.describe(apuesta="Cantidad de dinero a apostar.")
    async def blackjack(self, interaction: discord.Interaction, apuesta: int):
        """Descuenta la apuesta, reparte cartas y abre la vista de la mano."""
        if apuesta <= 0:
            await interaction.response.send_message(
                "🔸 La apuesta debe ser un número entero mayor que 0.", ephemeral=True
            )
            return

        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

        dinero = int(jugador.get("dinero", 0) or 0)
        if dinero < apuesta:
            await interaction.response.send_message(
                "❌ No tienes suficiente dinero para esa apuesta. Tu saldo: $" + str(dinero) + ".",
                ephemeral=True,
            )
            return

        mazo = crear_mazo()
        # Se reparte desde el inicio del mazo (pop(0)); el orden interno no
        # importa porque crear_mazo() lo devuelve barajado.
        mano_jugador = [mazo.pop(0), mazo.pop(0)]
        mano_dealer = [mazo.pop(0), mazo.pop(0)]

        # La apuesta se descuenta al inicio; los pagos van al final.
        jugadores_repo.actualizar_campo(interaction.user.id, "dinero", dinero - apuesta)

        vista = VistaBlackjack(interaction.user.id, mano_jugador, mano_dealer, mazo, apuesta)
        await interaction.response.defer()

        # Blackjack natural del jugador: se resuelve al momento.
        if valor_mano(mano_jugador) == 21:
            fresco = jugadores_repo.get_jugador(interaction.user.id)
            dinero_actual = int((fresco or {}).get("dinero", 0) or 0)
            if valor_mano(mano_dealer) == 21:
                jugadores_repo.actualizar_campo(interaction.user.id, "dinero", dinero_actual + apuesta)
                nota = "🤝 Ambos tienen blackjack. Recuperas tu apuesta."
            else:
                ganancia = int(apuesta * 1.5)  # pago 3:2
                jugadores_repo.actualizar_campo(
                    interaction.user.id, "dinero", dinero_actual + apuesta + ganancia
                )
                nota = "🃏 ¡Blackjack natural! Ganas $" + str(ganancia) + " (pago 3:2)."
            vista.terminado = True
            vista._deshabilitar_todo()
            mensaje = await interaction.followup.send(
                embed=vista.construir_embed(revelar_dealer=True, nota=nota), view=vista
            )
            vista.message = mensaje
            return

        mensaje_inicial = await interaction.followup.send(embed=vista.construir_embed(), view=vista)
        vista.message = mensaje_inicial


async def setup(bot: commands.Bot):
    await bot.add_cog(BlackJack(bot))
