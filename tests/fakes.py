"""Objetos falsos de Discord para probar comandos sin conexión.

FabricaInteraccion construye interacciones que imitan discord.Interaction:
capturan respuestas, followups y ediciones en listas simples que los tests
revisan. También crea Members/Guilds/TextChannels falsos.
"""

import sys
from unittest.mock import MagicMock

import pytest_asyncio

sys.path.insert(0, "tests")


class RespuestaCapturada:
    """Guarda lo enviado por interaction.response.send_message/edit_message."""

    def __init__(self):
        self.mensajes = []
        self.ediciones = []
        self.enviado = False  # ya se respondió la interacción

    async def send_message(self, content=None, *, embed=None, view=None, ephemeral=False, file=None, files=None):
        self.enviado = True
        self.mensajes.append(
            {"content": content, "embed": embed, "view": view, "ephemeral": ephemeral, "file": file, "files": files}
        )

    async def defer(self, *, ephemeral=False, thinking=False):
        self.enviado = True

    async def edit_message(self, *, content=None, embed=None, view=None, attachments=None):
        self.ediciones.append({"content": content, "embed": embed, "view": view})


class FollowupCapturado:
    def __init__(self):
        self.mensajes = []

    async def send(self, content=None, *, embed=None, view=None, ephemeral=False, file=None, files=None, wait=True):
        self.mensajes.append(
            {"content": content, "embed": embed, "view": view, "ephemeral": ephemeral, "file": file, "files": files}
        )


class MensajeFake:
    """Mensaje de Discord falso, para listeners tipo on_message."""

    def __init__(self, content="", author=None, channel=None, guild=None):
        self.content = content
        self.author = author
        self.channel = channel
        self.guild = guild if guild is not None else getattr(channel, "guild", None)
        self.mentions = []
        self.reference = None  # no es respuesta a nadie por defecto
        self.ediciones = []
        self.borrado = False
        from unittest.mock import MagicMock

        async def _edit(*args, **kwargs):
            self.ediciones.append(kwargs)

        async def _delete(*args, **kwargs):
            self.borrado = True

        self.edit = _edit
        self.delete = _delete
        self._magic = MagicMock()

    @property
    def created_at(self):  # por si algun cog la usa
        import datetime

        return datetime.datetime(2026, 1, 1)


class CanalCapturador:
    """Canal de texto falso que registra todo lo enviado con send()."""

    def __init__(self, channel_id=200, guild=None, name="canal-prueba"):
        self.id = channel_id
        self.guild = guild
        self.name = name
        self.mention = "<#" + str(channel_id) + ">"
        self.category_id = None
        self.topic = None
        self.mensajes_enviados = []  # cada send() deja un dict aqui
        self.archivos = []

    async def send(self, content=None, *, embed=None, file=None, files=None, view=None,
                   delete_after=None, reference=None, mention_author=None, embeds=None):
        registro = {
            "content": content, "embed": embed, "embeds": embeds, "view": view,
            "file": file, "files": files, "delete_after": delete_after,
        }
        self.mensajes_enviados.append(registro)
        if file is not None:
            self.archivos.append(file)
        mensaje = MensajeFake(content=str(content) if content else "", author=None, channel=self, guild=self.guild)
        return mensaje


class CategoriaFake(CanalCapturador):
    """CategoryChannel falso: tiene canales hijos."""

    def __init__(self, category_id=300, guild=None, name="categoria-prueba"):
        super().__init__(channel_id=category_id, guild=guild, name=name)
        self.canales_hijos = []

    @property
    def channels(self):
        return self.canales_hijos

    async def create_text_channel(self, name, **kwargs):
        nuevo = CanalCapturador(channel_id=len(self.canales_hijos) + 900, guild=self.guild, name=name)
        self.canales_hijos.append(nuevo)
        return nuevo


class VoiceClientFalso:
    """VoiceClient falso: reproduce sin conectar a nada."""

    def __init__(self):
        self.reproduciendo = None  # fuente asignada a play()
        self.pausado = False
        self.desconectado = False
        self.is_playing_calls = 0
        self.is_connected_calls = 0
        self.is_paused_calls = 0
        from unittest.mock import MagicMock

        self.stop = MagicMock()

    async def disconnect(self, **kwargs):
        self.desconectado = True

    async def move_to(self, canal, **kwargs):
        self.canal_actual = canal

    def play(self, fuente, **kwargs):
        self.reproduciendo = fuente
        self.after = kwargs.get("after")

    def is_playing(self):
        self.is_playing_calls += 1
        return self.reproduciendo is not None and not self.pausado

    def is_paused(self):
        self.is_paused_calls += 1
        return self.pausado

    def pause(self):
        self.pausado = True

    def resume(self):
        self.pausado = False

    def is_connected(self):
        self.is_connected_calls += 1
        return not self.desconectado


class TrackFalso:
    """Pista de audio falsa para probar colas de musica."""

    def __init__(self, titulo="cancion", url="https://example.com/cancion", duracion=180, pide_quien=None):
        self.title = titulo
        self.url = url
        self.duration = duracion
        self.requester = pide_quien


class FabricaInteraccion:
    """Crea objetos fake reutilizables entre tests."""

    @staticmethod
    def funcion_original(metodo):
        """Dado un metodo del cog, devuelve su funcion async ejecutable.

        Los comandos @app_commands.command quedan como objetos Command que
        no se pueden llamar directo; el callback original vive en .callback.
        """
        return getattr(metodo, "callback", metodo)

    @classmethod
    async def invocar(cls, cog, nombre_metodo, interaccion, *args, **kwargs):
        """Ejecuta un comando del cog pasandole la interaccion falsa.

        Sirve tanto para metodos normales como para comandos envueltos
        en app_commands.Command.
        """
        funcion = cls.funcion_original(getattr(cog, nombre_metodo))
        return await funcion(cog, interaccion, *args, **kwargs)

    @staticmethod
    def rol(role_id: int = 500, nombre="rol-prueba"):
        from unittest.mock import MagicMock

        rol = MagicMock()
        rol.id = role_id
        rol.name = nombre
        rol.mention = "<@&" + str(role_id) + ">"
        return rol

    @staticmethod
    def miembro(user_id: int = 1, nombre: str = "tester", voice_channel=None):
        miembro = MagicMock()
        miembro.id = user_id
        miembro.name = nombre
        miembro.display_name = nombre
        miembro.mention = "<@%d>" % user_id
        miembro.bot = False
        miembro.guild = None  # se asigna con servidor()
        if voice_channel is not None:
            voz = MagicMock()
            voz.channel = voice_channel
            miembro.voice = voz
        else:
            miembro.voice = None
        avatar = MagicMock()
        avatar.url = "https://example.com/avatar.png"
        miembro.display_avatar = avatar
        return miembro

    @staticmethod
    def miembro_con_roles(user_id: int = 1, nombre: str = "tester", ids_roles=None, bot=False):
        """Miembro que tiene roles (lista de ids)."""
        miembro = FabricaInteraccion.miembro(user_id=user_id, nombre=nombre)
        miembro.bot = bot
        miembro.roles = [FabricaInteraccion.rol(role_id=i, nombre="rol-" + str(i)) for i in (ids_roles or [])]
        return miembro

    @staticmethod
    def servidor(guild_id: int = 100, con_voz=False, member_count=10):
        guild = MagicMock()
        guild.id = guild_id
        guild.name = "Servidor de prueba"
        guild.get_channel.return_value = None
        guild.get_member.return_value = None
        guild.member_count = member_count
        guild.me = FabricaInteraccion.miembro(user_id=999999, nombre="BotPrueba")
        if con_voz:
            guild.voice_client = VoiceClientFalso()
        else:
            guild.voice_client = None
        return guild

    @staticmethod
    def canal(channel_id: int = 200, guild=None, category_id=None, topic=None,
             capturador=False, name="canal-prueba"):
        if capturador:
            # Canal que registra los send() y sirve para listeners on_message
            canal = CanalCapturador(channel_id=channel_id, guild=guild, name=name)
            canal.category_id = category_id
            canal.topic = topic
            return canal
        from unittest.mock import MagicMock

        canal = MagicMock()
        canal.id = channel_id
        canal.guild = guild
        canal.category_id = category_id
        canal.topic = topic
        canal.name = name
        canal.mention = "<#%d>" % channel_id
        return canal

    @staticmethod
    def mensaje(content="", author=None, channel=None, guild=None, menciona_a=None, respuesta_a=None):
        """Mensaje falso para listeners on_message."""
        mensaje = MensajeFake(content=content, author=author, channel=channel, guild=guild)
        mensaje.mentions = list(menciona_a or [])
        mensaje.reference = respuesta_a
        return mensaje

    @classmethod
    def interaccion(cls, user_id: int = 1, guild=None, channel=None, nombre="tester"):
        """Construye una Interaction falsa lista para pasarla a un comando."""
        usuario = cls.miembro(user_id=user_id, nombre=nombre)
        usuario.roles = []  # lista vacia por defecto; usar miembro_con_roles para otros casos
        if guild is not None:
            usuario.guild = guild
        interaccion = MagicMock()
        interaccion.user = usuario
        interaccion.guild = guild
        interaccion.channel = channel if channel is not None else cls.canal(guild=guild)
        interaccion.response = RespuestaCapturada()
        interaccion.followup = FollowupCapturado()
        interaccion.client = MagicMock()

        # original_response() devuelve un mensaje editable fake
        mensaje_original = MagicMock()
        mensaje_original.edit = MagicMock()
        import asyncio

        async def _orig():
            return mensaje_original

        interaccion.original_response = _orig
        return interaccion


# Fixture directo para tests que solo necesitan una interacción simple
@pytest_asyncio.fixture
async def interaccion_simple(db_local):
    return FabricaInteraccion.interaccion(user_id=42)
