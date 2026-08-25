"""Servicio de IA con Cohere: responde cuando mencionan al bot.

En el bot viejo la clase IA vivía en ia.py, pero ese archivo solo imprimía
versiones de librerías (el import `from ia import IA` era imposible). Aquí
está la implementación real y funcional.
"""

import os

import cohere


class IaChat:
    """Wrapper mínimo sobre el cliente de Cohere."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("COHERE_API_KEY", "")
        self._client = None

    def _get_client(self):
        # Se crea perezosamente para no romper si no hay clave (ej. en tests)
        if self._client is None:
            self._client = cohere.Client(self.api_key)
        return self._client

    def chat(self, texto: str) -> str:
        client = self._get_client()
        response = client.chat(message=texto)
        return response.text
