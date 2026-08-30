"""Cog /trabajos: lista paginada de los trabajos disponibles."""

import discord
from discord import app_commands
from discord.ext import commands

from utils import datos

TRABAJOS_POR_PAGINA = 8
TIEMPO_DE_VISTA = 300  # segundos


class VistaTrabajos(discord.ui.View):
    """Paginacion de trabajos con botones para el autor de la lista."""

    def __init__(self, trabajos: list, autor_id: int):
        super().__init__(timeout=TIEMPO_DE_VISTA)
        self.trabajos = trabajos
        self.autor_id = autor_id
        self.pagina = 0
        self.ultima_pagina = max(0, (len(trabajos) - 1) // TRABAJOS_POR_PAGINA)
        self.message = None
        self._actualizar_botones()

    def _actualizar_botones(self):
        self.boton_anterior.disabled = self.pagina == 0
        self.boton_siguiente.disabled = self.pagina == self.ultima_pagina

    def construir_embed(self) -> discord.Embed:
        """Arma el embed de la pagina actual."""
        inicio = self.pagina * TRABAJOS_POR_PAGINA
        chunk = self.trabajos[inicio : inicio + TRABAJOS_POR_PAGINA]
        descripcion = (
            "Pagina "
            + str(self.pagina + 1)
            + "/"
            + str(self.ultima_pagina + 1)
            + " - "
            + str(len(self.trabajos))
            + " trabajos en total"
        )
        embed = discord.Embed(title="💼 Trabajos disponibles", description=descripcion, color=0x2F3136)
        for job in chunk:
            nombre = str(job.get("name", "Desconocido"))
            emoji = str(job.get("emoji", ""))
            titulo = nombre if not emoji else emoji + " " + nombre
            turnos = int(job.get("turnos_sugeridos") or 3)
            riesgoso = "Si" if int(job.get("es_riesgoso") or 0) else "No"
            valor = (
                "Nivel: **"
                + str(job.get("level", "?"))
                + "** - XP requerida: **"
                + str(datos.experiencia_requerida(job))
                + "** - Sueldo: **$"
                + str(datos.sueldo_base(job))
                + " por sesion**\n"
                + "Turnos: **"
                + str(turnos)
                + "** - Riesgo: **"
                + riesgoso
                + "**"
            )
            embed.add_field(name=titulo, value=valor, inline=False)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Solo el autor de la lista puede usar los botones."""
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Solo quien abrió la lista puede usar estos botones.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def boton_anterior(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        if self.pagina > 0:
            self.pagina -= 1
        self._actualizar_botones()
        await interaction_btn.response.edit_message(embed=self.construir_embed(), view=self)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def boton_siguiente(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        if self.pagina < self.ultima_pagina:
            self.pagina += 1
        self._actualizar_botones()
        await interaction_btn.response.edit_message(embed=self.construir_embed(), view=self)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def boton_cerrar(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction_btn.response.edit_message(content="Lista cerrada.", embed=None, view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            if self.message is not None:
                await self.message.edit(view=self)
        except discord.HTTPException:
            pass


class Trabajos(commands.Cog):
    """Muestra los trabajos a los que se puede postular el jugador."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trabajos", description="Ver los trabajos disponibles.")
    async def trabajos(self, interaction: discord.Interaction):
        """Envia la lista paginada de trabajos."""
        trabajos = datos.obtener_trabajos()
        if not trabajos:
            await interaction.response.send_message("No hay trabajos disponibles.", ephemeral=True)
            return

        vista = VistaTrabajos(trabajos, interaction.user.id)
        await interaction.response.defer()
        mensaje = await interaction.followup.send(embed=vista.construir_embed(), view=vista)
        vista.message = mensaje


async def setup(bot: commands.Bot):
    await bot.add_cog(Trabajos(bot))
