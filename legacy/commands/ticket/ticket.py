import discord
from discord.ext import commands
from discord import app_commands
from database.ticket_repo import get_ticket_channel, set_ticket_channel  # tu DB para categoría de tickets

# ------------------ VIEW DE BOTONES ------------------
class TicketView(discord.ui.View):
    def __init__(self, author: discord.Member, ticket_category_id: int):
        super().__init__(timeout=None)
        self.author = author
        self.ticket_category_id = ticket_category_id  # categoría para validar tickets

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.blurple, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"🟦 Ticket reclamado por {interaction.user.mention}",
        )
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild

        # Validar que sea un ticket
        if channel.category_id != self.ticket_category_id:
            await interaction.response.send_message(
                "❌ Este canal no es un ticket, no puedes cerrarlo.", ephemeral=True
            )
            return

        reason = "Sin motivo"  # por defecto

        # Obtener al creador desde el topic
        ticket_author = None
        if channel.topic:
            try:
                creator_id = int(channel.topic)
                ticket_author = guild.get_member(creator_id)
            except:
                pass

        # Notificar al creador por MD
        if ticket_author:
            try:
                await ticket_author.send(
                    f"✅ Tu ticket **{channel.name}** ha sido cerrado.\n**Motivo:** {reason}"
                )
            except:
                pass  # Si no acepta MD

        # Notificar al canal de logs del staff
        STAFF_CHANNEL_ID = 123456789012345678  # reemplaza con tu canal de logs
        staff_channel = guild.get_channel(STAFF_CHANNEL_ID)
        if staff_channel:
            await staff_channel.send(
                f"❌ Ticket **{channel.name}** cerrado por {interaction.user.mention}\n**Motivo:** {reason}"
            )

        # Mensaje efímero al staff que presionó el botón
        await interaction.response.send_message("✅ Cerrando ticket...", ephemeral=True)

        # Finalmente eliminar el canal
        await channel.delete(reason=f"Ticket cerrado por {interaction.user} | {reason}")
# ------------------ COG DE TICKETS ------------------
class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------ COMANDO PARA CONFIGURAR CATEGORÍA ------------------
    @app_commands.command(name="setticket", description="Configura la categoría donde se crearán los tickets")
    @app_commands.describe(category="Selecciona la categoría para los tickets")
    async def setticket(self, interaction: discord.Interaction, category: discord.abc.GuildChannel):
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ Debes seleccionar una categoría válida.", ephemeral=True
            )
            return

        set_ticket_channel(interaction.guild.id, category.id)
        await interaction.response.send_message(
            f"✅ Categoría de tickets configurada en {category.name}", ephemeral=True
        )

    @app_commands.command(name="ticket", description="Crea un ticket privado")
    @app_commands.describe(reason="Motivo opcional del ticket")
    async def ticket(self, interaction: discord.Interaction, reason: str = "No especificado"):
        guild = interaction.guild
        ticket_category_id = get_ticket_channel(guild.id)  # tu función para obtener categoría de tickets

        if not ticket_category_id:
            await interaction.response.send_message(
                "❌ No se ha configurado una categoría de tickets.", ephemeral=True
            )
            return

        category = guild.get_channel(ticket_category_id)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ La categoría configurada ya no es válida.", ephemeral=True
            )
            return

        # Configurar permisos
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Crear canal con topic = ID del creador
        ticket_name = f"ticket-{interaction.user.name}".lower()
        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=str(interaction.user.id),  # <--- ID del creador guardado aquí
            reason=f"Ticket creado por {interaction.user}"
        )

        # Mencion al autor
        await channel.send(f"{interaction.user.mention}")


        # Embed inicial
        embed = discord.Embed(
            title="🎫 Ticket creado",
            description=f"{interaction.user.mention} abrió este ticket.\n**Motivo:** {reason}",
            color=0x00ff88
        )

        # Añadir botones Claim + Close
        view = TicketView(author=interaction.user, ticket_category_id=ticket_category_id)
        await channel.send(embed=embed, view=view)

        # Responder al usuario
        await interaction.response.send_message(
            f"✅ Tu ticket ha sido creado: {channel.mention}", ephemeral=True
        )

    # ------------------ COMANDO PARA CERRAR TICKET MANUALMENTE ------------------
    @app_commands.command(name="closeticket", description="Cierra un ticket manualmente")
    @app_commands.describe(reason="Motivo opcional del cierre")
    async def closeticket(
        self,
        interaction: discord.Interaction,
        reason: str = None  # argumento opcional
    ):
        channel = interaction.channel
        guild = interaction.guild
        ticket_category_id = get_ticket_channel(guild.id)  # categoría de tickets configurada

        # Validar que sea un ticket
        if channel.category_id != ticket_category_id:
            await interaction.response.send_message(
                "❌ Este canal no es un ticket, no puedes cerrarlo.", ephemeral=True
            )
            return

        reason_text = reason or "Sin motivo"

        # Obtener al creador del ticket usando el topic
        ticket_author = None
        if channel.topic:
            try:
                creator_id = int(channel.topic)
                ticket_author = guild.get_member(creator_id)
            except:
                pass

        # Notificar al creador por MD
        if ticket_author:
            try:
                await ticket_author.send(
                    f"✅ Tu ticket **{channel.name}** ha sido cerrado.\n**Motivo:** {reason_text}"
                )
            except:
                pass  # si no acepta MD

        # Notificar al canal de logs del staff
        STAFF_CHANNEL_ID = 123456789012345678  # reemplaza con tu canal de logs
        staff_channel = guild.get_channel(STAFF_CHANNEL_ID)
        if staff_channel:
            await staff_channel.send(
                f"❌ Ticket **{channel.name}** cerrado por {interaction.user.mention}\n**Motivo:** {reason_text}"
            )

        # Mensaje efímero al staff que cerró
        await interaction.response.send_message(
            f"✅ Ticket cerrado con motivo: {reason_text}", ephemeral=True
        )

        # Eliminar el canal
        await channel.delete(reason=f"Ticket cerrado por {interaction.user} | {reason_text}")


# ------------------ SETUP ------------------
async def setup(bot):
    await bot.add_cog(Ticket(bot))