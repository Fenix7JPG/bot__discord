"""Respuesta con IA cuando mencionan al bot."""

import discord
from discord.ext import commands

from services.ia import IaChat


class IaChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ia: IaChat | None = None  # se crea perezosamente al primer uso

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if self.bot.user not in message.mentions:
            return
        if message.reference:  # es una respuesta a otro mensaje, ignorar
            return
        if message.content.startswith("!"):
            return

        pregunta = message.content.replace("<@" + str(self.bot.user.id) + ">", "").strip()
        if not pregunta:
            pregunta = "Hola"

        if self.ia is None:
            self.ia = IaChat()

        try:
            respuesta = await self._consultar(pregunta)
        except Exception:
            respuesta = "La IA no esta disponible ahora mismo."

        await message.reply(respuesta)

    async def _consultar(self, pregunta: str) -> str:
        # Cohere es bloqueante: correr en un hilo para no trabar el bot
        import asyncio

        return await asyncio.to_thread(self.ia.chat, pregunta)


async def setup(bot):
    await bot.add_cog(IaChatCog(bot))
