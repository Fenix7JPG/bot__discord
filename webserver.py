"""Mini servidor web del bot.

Dos funciones:
1. Keep-alive para Render: responde en el puerto asignado.
2. Visor de terminal: la raiz muestra "El bot esta vivo"; si se envia la
   contrasena correcta (variable LOG_PASSWORD) en /terminal se muestran los
   ultimos registros del bot para depurar errores sin acceso a la consola.

Si la propia pagina del visor falla, el traceback se muestra en la respuesta
(para poder depurar sin acceso a consola).

instalar_captura_logs() redirige print()/stderr y engancha el modulo logging
a un buffer circular en memoria. Se llama desde bot.py antes de cargar cogs.
"""

import html
import logging
import os
import secrets
import sys
import threading
import traceback
from collections import deque

from flask import Flask, request

from config import settings

app = Flask(__name__)

# Marca para saber que version del visor esta desplegada
VISOR_VERSION = "v4"

# Ultimas lineas de registro conservadas en memoria
MAX_LINEAS = 500
_buffer: deque[str] = deque(maxlen=MAX_LINEAS)
_lock = threading.Lock()

# Traceback del ultimo error interno del visor (para mostrarlo en pantalla)
_ultimo_error = ""


def _asegurar_texto(texto) -> str:
    """Convierte cualquier cosa a str seguro para una respuesta HTTP.

    Elimina surrogates y caracteres que rompen la codificacion UTF-8,
    causa tipica de errores 500 al servir registros capturados.
    """
    try:
        s = str(texto)
    except Exception:
        return "<objeto ilegible>"
    return s.encode("utf-8", "replace").decode("utf-8")


def _agregar_linea(texto) -> None:
    texto_seguro = _asegurar_texto(texto)
    for linea in texto_seguro.splitlines():
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

    def write(self, texto):
        try:
            self._original.write(texto)
        except Exception:
            pass
        if texto and str(texto).strip():
            _agregar_linea(texto)
        return len(str(texto))

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
    print("[visor] activo, version " + VISOR_VERSION)


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------
# El contenido dinamico se inserta por CONCATENACION sobre cadenas ya
# sanitizadas con _asegurar_texto(); nunca .format() sobre datos externos.

_ESTILO = (
    "<style>"
    "body{background:#0d1117;color:#c9d1d9;font-family:monospace;padding:24px}"
    ".term{background:#010409;border:1px solid #30363d;border-radius:8px;"
    "padding:16px;white-space:pre-wrap;word-break:break-all;font-size:13px;line-height:1.45}"
    "input{background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:8px}"
    "button{background:#238636;color:#fff;border:none;border-radius:6px;padding:8px 14px;cursor:pointer}"
    ".error{color:#f85149}.pie{color:#8b949e;font-size:11px;margin-top:18px}"
    "</style>"
)

_PIE = "<p class=\"pie\">visor " + VISOR_VERSION + "</p>"


def _pagina_formulario(mensaje_error: str) -> str:
    pagina = (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>Bot - estado</title>" + _ESTILO + "</head><body>"
        "<h2>El bot esta vivo.</h2>"
        "<p>Aqui no hay nada que ver. Si eres el administrador, escribe la contrasena "
        "para abrir la terminal.</p>"
        '<form method="post" action="/terminal">'
        '<input type="password" name="clave" placeholder="contrasena" autofocus>'
        '<button type="submit">Abrir terminal</button>'
    )
    if mensaje_error:
        pagina = pagina + '<p class="error">' + mensaje_error + "</p>"
    return pagina + "</form>" + _PIE + "</body></html>"


@app.route("/")
def index():
    return "El bot esta vivo."


@app.route("/terminal", methods=["GET", "POST"])
def terminal():
    global _ultimo_error
    try:
        return _pagina_terminal()
    except Exception:
        # Ante cualquier imprevisto MOSTRAR el traceback en pantalla:
        # es la unica consola disponible en Render gratuito.
        _ultimo_error = traceback.format_exc()
        detalle = html.escape(_asegurar_texto(_ultimo_error))
        _agregar_linea("[visor] error interno mostrado al usuario")
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            "<title>Error del visor</title>" + _ESTILO + "</head><body>"
            '<p class="error">Ocurrio un error mostrando la terminal.'
            " Este es el detalle tecnico:</p>"
            '<div class="term">' + detalle + "</div>"
            '<p><a href="/">Volver</a></p>' + _PIE + "</body></html>"
        )


def _pagina_terminal():
    clave = request.values.get("clave", "")
    if not clave:
        # GET o formulario vacio: mostrar el formulario
        return _pagina_formulario("")

    if not _clave_valida(clave):
        return _pagina_formulario("Contrasena incorrecta.")

    # Construir el bloque de registros protegiendo cada paso
    try:
        lineas = leer_lineas()
        cuerpo = html.escape(_asegurar_texto("\n".join(lineas)))
    except Exception as e:
        cuerpo = "(no se pudieron leer los registros: " + _asegurar_texto(e) + ")"

    if not cuerpo.strip():
        cuerpo = "(sin registros todavia)"

    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="5">'
        "<title>Terminal del bot</title>" + _ESTILO + "</head><body>"
        "<p>Actualizacion automatica cada 5 segundos. "
        '<a href="/">Volver</a></p>'
        '<div class="term">' + cuerpo + "</div>" + _PIE + "</body></html>"
    )


def _clave_valida(clave: str) -> bool:
    esperada = settings.log_password
    if not isinstance(esperada, str) or not esperada:
        return False  # sin contrasena configurada, terminal cerrada
    try:
        return secrets.compare_digest(
            str(clave).encode("utf-8"), esperada.encode("utf-8")
        )
    except Exception:
        return False


def _run():
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    hilo = threading.Thread(target=_run, daemon=True)
    hilo.start()
