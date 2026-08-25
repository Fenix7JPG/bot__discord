"""Comando mínimo usado solo por los tests para verificar el entorno."""

from database import jugadores_repo


async def comando_de_prueba(interaccion):
    await interaccion.response.send_message("pong")
