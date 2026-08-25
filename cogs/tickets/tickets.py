"""Sistema de tickets: canales privados de soporte con botones."""

import discord
from discord import app_commands
from discord.ext import commands

from database.servidor_repo import get_config, set_config


class VistaTicket(discord.ui.View):
    """Botones Reclamar y Cerrar dentro del canal del ticket."""

    def __init__(self, categoria_id: int):
        super().__init__(timeout=None)
        self.categoria_id = categoria_id

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.blurple, custom_id="claim_ticket")
    async def reclamar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket reclamado por " + interaction.user.mention)

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def cerrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _cerrar_ticket(interaction, motivo="Sin motivo")


async def _cerrar_ticket(interaction: discord.Interaction, motivo: str):
    """Valida que el canal sea un ticket, avisa al creador y borra el canal."""
    canal = interaction.channel
    guild = interaction.guild

    categoria_ticket = get_config(guild.id, "ticket_category_id")
    if canal.category_id != categoria_ticket:
        await interaction.response.send_message("Este canal no es un ticket, no puedes cerrarlo.", ephemeral=True)
        return

    # El ID del creador queda guardado en el topic del canal
    creador = None
    if canal.topic:
        try:
            creador = guild.get_member(int(canal.topic))
        except ValueError:
            creador = None

    if creador is not None:
        try:
            await creador.send(
                "Tu ticket **" + canal.name + "** ha sido cerrado.\nMotivo: " + motivo
            )
        except Exception:
            pass  # el usuario puede tener los MD cerrados

    # Log opcional en un canal llamado "logs" si existe
    canal_logs = discord.utils.get(guild.text_channels, name="logs")
    if canal_logs is not None:
        try:
            await canal_logs.send(
                "Ticket **" + canal.name + "** cerrado por "
                + interaction.user.mention + "\nMotivo: " + motivo
            )
        except Exception:
            pass

    await interaction.response.send_message("Cerrando ticket...", ephemeral=True)
    await canal.delete(reason="Ticket cerrado por " + str(interaction.user) + " | " + motivo)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setticket", description="Configura la categoria donde se crean los tickets.")
    @app_commands.describe(category="Categoria para los canales de ticket")
    @app_commands.default_permissions(administrator=True)
    async def setticket(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        set_config(interaction.guild.id, "ticket_category_id", category.id)
        await interaction.response.send_message(
            "Categoria de tickets configurada en **" + category.name + "**", ephemeral=True
        )

    @app_commands.command(name="ticket", description="Crea un ticket privado de soporte.")
    @app_commands.describe(motivo="Motivo opcional del ticket")
    async def ticket(self, interaction: discord.Interaction, motivo: str = "No especificado"):
        guild = interaction.guild
        categoria_id = get_config(guild.id, "ticket_category_id")

        if not categoria_id:
            await interaction.response.send_message(
                "No se ha configurado una categoria de tickets. Un admin debe usar /setticket.", ephemeral=True
            )
            return

        categoria = guild.get_channel(categoria_id)
        if not isinstance(categoria, discord.CategoryChannel):
            await interaction.response.send_message("La categoria configurada ya no es valida.", ephemeral=True)
            return

        permisos = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        canal = await guild.create_text_channel(
            name="ticket-" + interaction.user.name.lower(),
            category=categoria,
            overwrites=permisos,
            topic=str(interaction.user.id),  # ID del creador para el cierre
            reason="Ticket creado por " + str(interaction.user),
        )

        embed = discord.Embed(
            title="Ticket creado",
            description=interaction.user.mention + " abrio este ticket.\n**Motivo:** " + motivo,
            color=0x00FF88,
        )
        vista = VistaTicket(categoria_id)
        await canal.send(content=interaction.user.mention, embed=embed, view=vista)

        await interaction.response.send_message("Tu ticket ha sido creado: " + canal.mention, ephemeral=True)

    @app_commands.command(name="closeticket", description="Cierra el ticket actual manualmente.")
    @app_commands.describe(motivo="Motivo opcional del cierre")
    async def closeticket(self, interaction: discord.Interaction, motivo: str = "Sin motivo"):
        await _cerrar_ticket(interaction, motivo=motivo)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
