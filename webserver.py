"""Mini servidor web del bot.

Dos funciones:
1. Keep-alive para Render: responde en el puerto asignado.
2. Visor de terminal: la raiz muestra "El bot esta vivo"; si se envia la
   contrasena correcta (variable LOG_PASSWORD) en /terminal se muestran los
   ultimos registros del bot para depurar errores sin acceso a la consola.

instalar_captura_logs() redirige print()/stderr y engancha el modulo logging
a un buffer circular en memoria. Se llama desde bot.py antes de cargar cogs.
"""

import html
import logging
import os
import secrets
import sys
import threading
from collections import deque

from flask import Flask, request

from config import settings

app = Flask(__name__)

# Ultimas lineas de registro conservadas en memoria
MAX_LINEAS = 500
_buffer: deque[str] = deque(maxlen=MAX_LINEAS)
_lock = threading.Lock()


def _agregar_linea(texto: str) -> None:
    for linea in texto.splitlines():
        if linea.strip():
            with _lock:
                _buffer.append(linea.rstrip())


def leer_lineas() -> list[str]:
    with _lock:
        return list(_buffer)


class _Tee:
    """Escribe al stream original y guarda una copia en el buffer."""

    def __init__(self, original):
        self._original = original

    def write(self, texto: str):
        try:
            self._original.write(texto)
        except Exception:
            pass
        if texto and texto.strip():
            _agregar_linea(texto)
        return len(texto)

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass


class _BufferLogHandler(logging.Handler):
    """Guarda en el buffer los registros del modulo logging (discord.py etc.)."""

    def __init__(self):
        super().__init__()
        self.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s", "%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord):
        try:
            _agregar_linea(self.format(record))
        except Exception:
            pass


def instalar_captura_logs() -> None:
    """Empieza a capturar prints y logs del proceso en el buffer."""
    if isinstance(sys.stdout, _Tee):
        return  # ya instalado

    # Los pings de salud de Render llenarian el buffer de ruido
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr)
    logging.getLogger().addHandler(_BufferLogHandler())
    _agregar_linea("[visor] captura de logs iniciada")


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------

_ESTILO = (
    "<style>"
    "body{background:#0d1117;color:#c9d1d9;font-family:monospace;padding:24px}"
    ".term{background:#010409;border:1px solid #30363d;border-radius:8px;"
    "padding:16px;white-space:pre-wrap;word-break:break-all;font-size:13px;line-height:1.45}"
    "input{background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:8px}"
    "button{background:#238636;color:#fff;border:none;border-radius:6px;padding:8px 14px;cursor:pointer}"
    ".error{color:#f85149}"
    "</style>"
)

_PAGINA_FORM = """<!doctype html><html><head><meta charset="utf-8">
<title>Bot - estado</title>{estilo}</head><body>
<h2>El bot esta vivo.</h2>
<p>Aqui no hay nada que ver. Si eres el administrador, escribe la contrasena
para abrir la terminal.</p>
<form method="post" action="/terminal">
<input type="password" name="clave" placeholder="contrasena" autofocus>
<button type="submit">Abrir terminal</button>
{error}
</form></body></html>"""


@app.route("/")
def index():
    return "El bot esta vivo."


@app.route("/terminal", methods=["GET", "POST"])
def terminal():
    clave = request.form.get("clave", "")
    if not clave:
        # GET o formulario vacio: mostrar el formulario
        return _PAGINA_FORM.format(estilo=_ESTILO, error="")

    if not _clave_valida(clave):
        return _PAGINA_FORM.format(
            estilo=_ESTILO,
            error='<p class="error">Contrasena incorrecta.</p>',
        )

    lineas = html.escape("\n".join(leer_lineas())) or "(sin registros todavia)"
    pagina = """<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>Terminal del bot</title>{estilo}</head><body>
<p>Actualizacion automatica cada 5 segundos. <a href="/">Volver</a></p>
<div class="term">{lineas}</div>
</body></html>""".format(estilo=_ESTILO, lineas=lineas)
    return pagina


def _clave_valida(clave: str) -> bool:
    esperada = settings.log_password
    if not esperada:
        return False  # sin contrasena configurada, terminal cerrada
    return secrets.compare_digest(clave, esperada)


def _run():
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    hilo = threading.Thread(target=_run, daemon=True)
    hilo.start()
