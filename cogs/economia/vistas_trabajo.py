"""Vistas de Discord (botones) para el flujo de trabajo por turnos.

Solo interfaz: la logica vive en services/turnos_trabajo y el manejo de la
sesion en el cog Work. Las etiquetas de los botones no llevan emojis.
"""

import discord
from discord.ext import commands


class BotonOpcion(discord.ui.Button):
    """Un boton de opcion del turno actual."""

    def __init__(self, etiqueta: str, indice: int, fila: int):
        super().__init__(label=etiqueta, row=fila)
        self.indice = indice

    async def callback(self, interaction: discord.Interaction):
        vista = self.view
        await vista.manejar_respuesta(interaction, self.indice)


class VistaTurno(discord.ui.View):
    """Cuatro botones con las opciones de la pregunta actual.

    Solo el dueno de la sesion puede presionar; el cog procesa la respuesta
    y edita el mensaje (siguiente turno o resumen final).
    """

    def __init__(self, cog, user_id: int, pregunta: dict):
        super().__init__(timeout=180)  # 3 minutos, igual que la sesion
        self.cog = cog
        self.user_id = user_id
        for indice, opcion in enumerate(pregunta["opciones"]):
            self.add_item(BotonOpcion(str(opcion), indice, indice // 2))

    async def manejar_respuesta(self, interaction: discord.Interaction, indice: int):
        """Enruta la presion al cog; un tercero recibe un aviso efimero."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Esta sesion de trabajo no es tuya. Usa /work para jugar la tuya.",
                ephemeral=True,
            )
            return
        await self.cog.procesar_presion(interaction, indice)


class VistaConfirmarRenuncia(discord.ui.View):
    """Confirmacion para /renunciar-trabajo: Confirmar o Cancelar."""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id

    async def manejar_respuesta(self, interaction: discord.Interaction, confirmo: bool):
        """Enruta la decision al cog; un tercero recibe un aviso efimero."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Esta confirmacion no es tuya.", ephemeral=True
            )
            return
        await self.cog.procesar_confirmacion(interaction, confirmo)


class BotonConfirmar(discord.ui.Button):
    def __init__(self, vista: "VistaConfirmarRenuncia"):
        super().__init__(label="Confirmar", style=discord.ButtonStyle.danger)
        self._vista = vista

    async def callback(self, interaction: discord.Interaction):
        await self._vista.manejar_respuesta(interaction, True)


class BotonCancelar(discord.ui.Button):
    def __init__(self, vista: "VistaConfirmarRenuncia"):
        super().__init__(label="Cancelar", style=discord.ButtonStyle.secondary)
        self._vista = vista

    async def callback(self, interaction: discord.Interaction):
        await self._vista.manejar_respuesta(interaction, False)


def vista_confirmar_renuncia(cog, user_id: int) -> VistaConfirmarRenuncia:
    """Construye la vista de confirmacion con sus dos botones."""
    vista = VistaConfirmarRenuncia(cog, user_id)
    vista.add_item(BotonConfirmar(vista))
    vista.add_item(BotonCancelar(vista))
    return vista


async def setup(bot: commands.Bot):
    """No es un cog: el autocargador de bot.py exige setup() en cada archivo
    bajo cogs/; aqui no se registra ningun comando."""
    return None
