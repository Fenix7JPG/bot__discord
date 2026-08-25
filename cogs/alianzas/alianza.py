"""Sistema de alianzas: los cazadores pegan invites y suman puntos."""

import asyncio
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from database.servidor_repo import (
    add_point,
    get_config,
    get_points,
    get_position,
    get_ranking,
)

INVITE_REGEX = r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/([A-Za-z0-9]+)"


class Alianzas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -- configuracion -------------------------------------------------------

    def alianza_configurada(self, guild_id: int) -> bool:
        canal = get_config(guild_id, "alliance_channel_id")
        rol_cazador = get_config(guild_id, "hunter_role_id")
        rol_alianza = get_config(guild_id, "alliance_role_id")
        return bool(canal and rol_cazador and rol_alianza)

    def embed_no_configurado(self) -> discord.Embed:
        embed = discord.Embed(
            title="Sistema de alianzas no configurado",
            description="El sistema de alianzas aun no esta configurado en este servidor.",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="Configuracion requerida",
            value="`/setalianzachannel`\n`/setcazadorrol`\n`/setalianzarol`",
            inline=False,
        )
        embed.set_footer(text="Un administrador debe configurar el sistema.")
        return embed

    # -- resolucion del invite ----------------------------------------------

    async def obtener_nombre_servidor(self, codigo_invite: str) -> str | None:
        """Consulta la API de Discord por el nombre del server del invite."""
        url = "https://discord.com/api/v10/invites/" + codigo_invite + "?with_counts=true"
        headers = {"Authorization": "Bot " + self.bot.http.token}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as respuesta:
                if respuesta.status != 200:
                    return None
                datos = await respuesta.json()
                servidor = datos.get("guild")
                if servidor:
                    return servidor.get("name")
                return None

    # -- listener principal ----------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        if not self.alianza_configurada(guild_id):
            return

        canal_alianzas = get_config(guild_id, "alliance_channel_id")
        if message.channel.id != canal_alianzas:
            return

        rol_cazador_id = get_config(guild_id, "hunter_role_id")
        roles_autor = getattr(message.author, "roles", [])
        if not any(rol.id == rol_cazador_id for rol in roles_autor):
            return

        match = re.search(INVITE_REGEX, message.content)
        codigo_invite = match.group(1) if match else None
        nombre_servidor = None
        if codigo_invite:
            nombre_servidor = await self.obtener_nombre_servidor(codigo_invite)

        if not nombre_servidor:
            # Sin invite valido: avisar y limpiar ambos mensajes a los 8s
            aviso = await message.reply(embed=self.embed_invite_invalido())
            await asyncio.sleep(8)
            for mensaje_a_borrar in (message, aviso):
                try:
                    await mensaje_a_borrar.delete()
                except Exception:
                    pass
            return

        # Invite valido: sumar punto y anunciar
        add_point(guild_id, message.author.id)
        puntos = get_points(guild_id, message.author.id)
        posicion = get_position(guild_id, message.author.id)

        embed = discord.Embed(
            title="Nueva alianza realizada",
            color=discord.Color.dark_gray(),
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url,
        )
        embed.add_field(name="Cazador", value=message.author.mention, inline=False)
        embed.add_field(name="Servidor", value="**" + nombre_servidor + "**", inline=False)
        embed.add_field(name="Ranking", value="#" + str(posicion), inline=True)
        embed.add_field(name="Puntos", value="**" + str(puntos) + "**", inline=True)

        await message.reply(embed=embed)

    def embed_invite_invalido(self) -> discord.Embed:
        embed = discord.Embed(
            title="Alianza no valida",
            description="El mensaje no contiene una invitacion valida de Discord.",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Formato requerido",
            value=(
                "Debes enviar un link de invitacion.\n"
                "`https://discord.gg/xxxxx`\n"
                "`https://discord.com/invite/xxxxx`"
            ),
            inline=False,
        )
        return embed

    # -- comandos ---------------------------------------------------------------

    @app_commands.command(name="ranking_alianzas", description="Ver ranking de cazadores de alianzas.")
    async def ranking_alianzas(self, interaction: discord.Interaction):
        if interaction.guild is None or not self.alianza_configurada(interaction.guild.id):
            await interaction.response.send_message(embed=self.embed_no_configurado(), ephemeral=True)
            return

        ranking = get_ranking(interaction.guild.id)
        if not ranking:
            await interaction.response.send_message("Aun no hay alianzas registradas.")
            return

        texto = ""
        for i, fila in enumerate(ranking, start=1):
            medalla = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, str(i) + ".")
            texto += medalla + " <@" + str(fila["user_id"]) + "> - **" + str(fila["points"]) + "** alianzas\n"

        embed = discord.Embed(
            title="Ranking de Cazadores de Alianzas",
            description=texto,
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="alianzas_perfil", description="Ver tu progreso como cazador de alianzas.")
    async def alianzas_perfil(self, interaction: discord.Interaction):
        if interaction.guild is None or not self.alianza_configurada(interaction.guild.id):
            await interaction.response.send_message(embed=self.embed_no_configurado(), ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        puntos = get_points(guild_id, user_id)
        posicion = get_position(guild_id, user_id)
        texto_posicion = "#" + str(posicion) if posicion is not None else "Sin ranking aun"

        embed = discord.Embed(title="Perfil de Cazador de Alianzas", color=discord.Color.blue())
        embed.add_field(name="Usuario", value=interaction.user.mention, inline=False)
        embed.add_field(name="Posicion", value=texto_posicion, inline=True)
        embed.add_field(name="Alianzas hechas", value="**" + str(puntos) + "**", inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Alianzas(bot))
