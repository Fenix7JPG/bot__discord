# cogs/admin.py
import discord
from discord.ext import commands

class StopAll(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    # --- EL COMANDO MÁGICO ---
    @commands.command(name="nukevoice", hidden=True)
    @commands.is_owner()
    async def nukevoice(self, ctx: commands.Context):
        """
        Desconecta al bot por la fuerza de TODOS los canales de voz de TODOS los servidores.
        Ideal para limpiar estados 'fantasma' o 'dobles'.
        """
        await ctx.send("💣 Iniciando protocolo de desconexión de voz global")

        disconnected = 0
        failed = 0

        # Iteramos sobre todos los servidores donde el bot está
        for guild in self.bot.guilds:
            # Usamos guild.me para obtener el objeto Member del bot en ese servidor
            bot_member = guild.me
            if bot_member.voice: # Si el bot (miembro) está en un canal de voz
                try:
                    # Método 1: Intentar moverlo a None (la forma más forceful)
                    await bot_member.move_to(None)
                    print(f"[NUKEVOICE] Desconectado de '{guild.name}' (move_to None)")
                    disconnected += 1
                except discord.HTTPException as e:
                    # Método 2: Si move_to falla, intentamos desconectar de la forma normal
                    try:
                        voice_client = guild.voice_client
                        if voice_client:
                            await voice_client.disconnect(force=True)
                            print(f"[NUKEVOICE] Desconectado de '{guild.name}' (disconnect force=True)")
                            disconnected += 1
                        else:
                            print(f"[NUKEVOICE] Advertencia: No se encontró voice_client en '{guild.name}'")
                    except Exception as e2:
                        print(f"[NUKEVOICE] ERROR CRÍTICO al desconectar de '{guild.name}': {e2}")
                        failed += 1
                except Exception as e:
                    print(f"[NUKEVOICE] ERROR INESPERADO en '{guild.name}': {e}")
                    failed += 1

        await ctx.send(
            f"💣 Protocolo completado.\n"
            f"🔌 Desconectado de **{disconnected}** canales de voz.\n"
            f"❌ Falló en **{failed}** canales."
        )
# --- FUNCIÓN DE CONFIGURACIÓN ---
async def setup(bot: commands.Bot):
    await bot.add_cog(StopAll(bot))