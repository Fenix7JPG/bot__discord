import discord
from discord import app_commands
from discord.ext import commands

from database.alianzas_repo import add_point, get_alianza_role, get_points, get_position,get_ranking, get_alianza_channel, get_cazador_role



class Alianzas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    def alianza_configurada(self,guild_id):
        canal = get_alianza_channel(guild_id)
        rol_cazador = get_cazador_role(guild_id)
        rol_alianza = get_alianza_role(guild_id)
        return bool(canal and rol_cazador and rol_alianza)
    def embed_alianza_no_configurada(self):
        embed = discord.Embed(
            title="⚠ Sistema de alianzas no configurado",
            description="El sistema de alianzas aún no está configurado en este servidor.",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="📌 Configuración requerida",
            value=(
                "`/set_alianza_canal`\n"
                "`/set_cazador_rol`\n"
                "`/set_alianza_rol`"
            ),
            inline=False
        )

        embed.set_footer(text="Un administrador debe configurar el sistema.")

        return embed
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        if not message.guild:
            return
        

        if not self.alianza_configurada(message.guild.id):
            return
        
        # Verificar que el mensaje se envió en el canal de alianzas
        if message.channel.id != get_alianza_channel(message.guild.id):
            return
        
        # Verificar que el autor tenga el rol de cazador
        if not any(role.id == get_cazador_role(message.guild.id) for role in message.author.roles):
            return

        # sumar punto
        add_point(message.guild.id, message.author.id)

        puntos = get_points(message.guild.id, message.author.id)
        ranking = get_position(message.guild.id, message.author.id)


        embed = discord.Embed(
            title="‼ Nueva Alianza realizada 🐾",
            description="**Nueva alianza ✧**",
            color=discord.Color.dark_gray()
        )

        embed.add_field(
            name="💎 Cazador",
            value=message.author.mention,
            inline=False
        )

        embed.add_field(
            name="📍 Ranking",
            value=f"**#{ranking}**",
            inline=True
        )

        embed.add_field(
            name="⭐ Puntos",
            value=f"**{puntos}**",
            inline=True
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        embed.set_image(url="https://media.tenor.com/8dRk3G2A9E0AAAAC/anime-reading.gif")  # gif o imagen

        await message.reply(embed=embed)


    # Muestra el ranking de alianzas
    @app_commands.command(
    name="ranking_alianzas",
    description="Ver ranking de cazadores de alianzas"
    )
    async def ranking_alianzas(self, interaction: discord.Interaction):
        

        if not self.alianza_configurada(interaction.guild.id):

            await interaction.response.send_message(
            embed=self.embed_alianza_no_configurada(),
            ephemeral=True)
            return
            
        ranking = get_ranking(interaction.guild.id)

        if not ranking:
            await interaction.response.send_message(
                "Aún no hay alianzas registradas."
            )
            return

        texto = ""

        for i, (user_id, puntos) in enumerate(ranking, start=1):

            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."

            texto += f"{medal} <@{user_id}> — **{puntos}** alianzas\n"

        embed = discord.Embed(
            title="🏆 Ranking de Cazadores de Alianzas",
            description=texto,
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed)


    # Muestra el perfil del usuario con su posición y puntos
    @app_commands.command(
    name="alianzas_perfil",
    description="Ver tu progreso como cazador de alianzas"
    )
    async def alianzas_perfil(self, interaction: discord.Interaction):
        print("mmcccccck")

        # Verificar que el canal y roles estén configurados
        if not self.alianza_configurada(interaction.guild.id):

            await interaction.response.send_message(
            embed=self.embed_alianza_no_configurada(),
            ephemeral=True)
            return
            

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        


        puntos = get_points(guild_id, user_id)
        posicion = get_position(guild_id, user_id)

        if posicion is None:
            posicion = "Sin ranking aún"

        embed = discord.Embed(
            title="🏹 Perfil de Cazador de Alianzas",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="👤 Usuario",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="🏆 Posición",
            value=f"#{posicion}",
            inline=True
        )

        embed.add_field(
            name="🤝 Alianzas hechas",
            value=f"**{puntos}**",
            inline=True
        )

        await interaction.response.send_message(embed=embed)
async def setup(bot):
    await bot.add_cog(Alianzas(bot))