"""Prueba del visor web: captura, formulario, claves y contenido con llaves.

Uso: python scripts/probar_visor.py
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ["LOG_PASSWORD"] = "prueba123"

import importlib  # noqa: E402
import logging  # noqa: E402

import config  # noqa: E402
importlib.reload(config)

import webserver  # noqa: E402
importlib.reload(webserver)
webserver.instalar_captura_logs()

# Registros con contenido hostil: llaves de .format(), HTML, comillas
print("dict de prueba: {'clave': 'valor', 'otro': [1, 2]}")
print("<script>alert('xss')</script>")
logging.getLogger("discord.gateway").warning("Shard ID None heartbeat bloqueado {algo=1}")

cliente = webserver.app.test_client()

r = cliente.get("/")
assert r.status_code == 200 and "El bot esta vivo" in r.get_data(as_text=True)
print("1. raiz OK")

r = cliente.post("/terminal", data={"clave": "mala"})
assert "incorrecta" in r.get_data(as_text=True)
print("2. clave mala rechazada OK")

r = cliente.post("/terminal", data={"clave": "prueba123"})
texto = r.get_data(as_text=True)
assert r.status_code == 200, "la terminal devolvio " + str(r.status_code)
# html.escape convierte llaves no, pero comillas simples si: {'clave'} -> {&#x27;clave&#x27;}
assert "{'clave'" not in texto and "&#x27;clave&#x27;" in texto, "faltan las llaves escapadas"
assert "&lt;script&gt;" in texto, "el HTML no se escapo"
assert "heartbeat" in texto, "falta el log de discord"
print("3. terminal OK con llaves {}, HTML escapado y logs de libreria")

r = cliente.post("/terminal", data={"clave": ""})
assert r.status_code == 200 and "Abrir terminal" in r.get_data(as_text=True)
print("4. formulario vacio muestra el formulario OK")

print("VISOR COMPLETO: todo OK")
