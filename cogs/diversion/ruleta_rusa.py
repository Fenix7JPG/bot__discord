"""Cog /ruleta-rusa: partida multijugador por canal."""

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

SEGUNDOS_POR_TURNO = 5.0


class PartidaRuletaRusa:
    """Estado y bucle de turnos de una partida en un canal."""

    def __init__(self, cog, canal: discord.TextChannel, iniciador):
        self.cog = cog
        self.canal = canal
        self.iniciador = iniciador
        self.players: list = []
        self.started = False
        self.camaras = [False] * 6
        self.indice_camaras = 0
        self.indice_turno = 0
        self.reinicio_evento = asyncio.Event()

    def texto_lista(self, empezando: bool = False) -> str:
        """Texto del mensaje de registro de jugadores."""
        lineas = ["**- RULETA RUSA -**", "Pulsa **Unirse** para entrar o **Abandonar** para salir."]
        if not self.players:
            lineas.append("\n**Jugadores (0):** (aún nadie)")
        else:
            nombres = ", ".join(p.display_name for p in self.players)
            lineas.append("\n**Jugadores (" + str(len(self.players)) + "):** " + nombres)
        if empezando:
            lineas.append("\n> El juego ha comenzado. ¡Suerte!")
        return "\n".join(lineas)

    async def agregar_jugador(self, user) -> bool:
        if self.started or any(p.id == user.id for p in self.players):
            return False
        miembro = user
        if not hasattr(user, "guild") or user.guild is None:
            try:
                miembro = await self.canal.guild.fetch_member(user.id)
            except (discord.HTTPException, AttributeError):
                miembro = user
        self.players.append(miembro)
        return True

    async def quitar_jugador(self, user) -> bool:
        if self.started:
            return False
        for p in self.players:
            if p.id == user.id:
                self.players.remove(p)
                return True
        return False

    def _recargar_arma(self):
        self.camaras = [False] * 6
        self.camaras[random.randrange(6)] = True
        self.indice_camaras = 0

    async def ejecutar_partida(self):
        """Bucle de turnos hasta que quede un solo jugador."""
        self.started = True
        if len(self.players) < 2:
            await self.canal.send("No hay suficientes jugadores. Juego cancelado.")
            self.limpiar()
            return

        orden = "\n".join(str(i + 1) + ". " + p.mention for i, p in enumerate(self.players))
        await self.canal.send("Orden de juego:\n" + orden)
        self._recargar_arma()

        while len(self.players) > 1:
            jugador_actual = self.players[self.indice_turno % len(self.players)]
            await self.canal.send(
                "🔫 **Turno de "
                + jugador_actual.mention
                + "** - se prepara para disparar... ("
                + str(int(SEGUNDOS_POR_TURNO))
                + "s)"
            )
            await self._esperar_con_reinicios()

            if self.camaras[self.indice_camaras]:
                await self.canal.send(
                    "💥 **" + jugador_actual.mention + "** se ha disparado. Ha muerto."
                )
                self.players = [p for p in self.players if p.id != jugador_actual.id]
                if len(self.players) <= 1:
                    break
                self._recargar_arma()
                self.indice_turno %= len(self.players)
                await self.canal.send("🔄 Se recarga el arma y la partida continúa.")
            else:
                await self.canal.send("🔒 **" + jugador_actual.mention + "** ha disparado y *vive*.")
                self.indice_camaras = (self.indice_camaras + 1) % 6
                self.indice_turno = (self.indice_turno + 1) % len(self.players)

        if len(self.players) == 1:
            await self.canal.send("🏆 **" + self.players[0].mention + "** es el último en pie. ¡Ganador!")
        else:
            await self.canal.send("No quedan jugadores. Fin del juego.")
        self.limpiar()

    async def _esperar_con_reinicios(self):
        """Espera el turno; cualquier mensaje en el canal reinicia los 5s."""
        while True:
            self.reinicio_evento.clear()
            try:
                await asyncio.wait_for(self.reinicio_evento.wait(), timeout=SEGUNDOS_POR_TURNO)
                continue
            except asyncio.TimeoutError:
                break

    def reiniciar_conteo(self):
        try:
            self.reinicio_evento.set()
        except Exception:
            pass

    def limpiar(self):
        self.cog.games.pop(self.canal.id, None)


class VistaRuletaRusa(discord.ui.View):
    """Botones para unirse a la partida antes de que empiece."""

    def __init__(self, game: PartidaRuletaRusa):
        super().__init__(timeout=None)
        self.game = game

    @discord.ui.button(label="Unirse", style=discord.ButtonStyle.success)
    async def unirse(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        agregado = await self.game.agregar_jugador(interaction_btn.user)
        if agregado:
            await interaction_btn.response.edit_message(content=self.game.texto_lista(), view=self)
        else:
            await interaction_btn.response.send_message(
                "Ya estás en la lista o el juego ya empezó.", ephemeral=True
            )

    @discord.ui.button(label="Abandonar", style=discord.ButtonStyle.danger)
    async def abandonar(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        quitado = await self.game.quitar_jugador(interaction_btn.user)
        if quitado:
            await interaction_btn.response.edit_message(content=self.game.texto_lista(), view=self)
        else:
            await interaction_btn.response.send_message(
                "No estabas en la lista o el juego ya empezó.", ephemeral=True
            )

    @discord.ui.button(label="Empezar", style=discord.ButtonStyle.primary)
    async def empezar(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        if self.game.started:
            await interaction_btn.response.send_message("El juego ya empezó.", ephemeral=True)
            return
        if len(self.game.players) < 2:
            await interaction_btn.response.send_message(
                "Se necesitan al menos 2 jugadores para empezar.", ephemeral=True
            )
            return

        for child in self.children:
            child.disabled = True
        await interaction_btn.response.edit_message(
            content=self.game.texto_lista(empezando=True), view=self
        )
        asyncio.create_task(self.game.ejecutar_partida())


class RuletaRusa(commands.Cog):
    """Agrupa las partidas activas por id de canal."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[int, PartidaRuletaRusa] = {}

    @app_commands.command(name="ruleta-rusa", description="Inicia una partida de ruleta rusa.")
    async def ruleta_rusa(self, interaction: discord.Interaction):
        """Crea la partida del canal con su mensaje de registro."""
        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel):
            await interaction.response.send_message(
                "Este comando solo puede usarse en un canal de texto.", ephemeral=True
            )
            return

        if canal.id in self.games:
            await interaction.response.send_message(
                "Ya hay una ruleta activa en este canal.", ephemeral=True
            )
            return

        game = PartidaRuletaRusa(self, canal, interaction.user)
        vista = VistaRuletaRusa(game)

        mensaje = await canal.send(content=game.texto_lista(), view=vista)
        game.mensaje_vista = mensaje
        self.games[canal.id] = game
        await interaction.response.send_message(
            "Se ha creado la ruleta. ¡Únete con los botones del mensaje!", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Si alguien habla en el canal de una partida, se reinicia el turno."""
        if message.author.bot or message.guild is None:
            return
        game = self.games.get(message.channel.id)
        if game is not None:
            game.reiniciar_conteo()


async def setup(bot: commands.Bot):
    await bot.add_cog(RuletaRusa(bot))
