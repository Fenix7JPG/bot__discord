"""Blueprint del dashboard web (/panel).

Login OAuth2 de Discord, lista de servidores administrados y edicion de la
configuracion (economia + ajustes generales) con auditoria. Frontend en
HTML/CSS/JS puro servido desde aqui (sin carpeta templates).

Para pruebas existe crear_app(): una app Flask minima con este blueprint.
En produccion el blueprint se registra sobre la app de webserver.py.
"""

import html
import secrets
import time
import urllib.parse
from pathlib import Path

from flask import Blueprint, Response, jsonify, redirect, request, session

from database import servidor_repo
from services.dashboard import auth, configurador

panel = Blueprint("panel", __name__)

DURACION_SESION = 12 * 3600  # 12 horas
RAIZ = Path(__file__).resolve().parents[2]

# Bot de Discord registrado (para saber en que servidores esta presente)
_bot = None


def registrar_bot(bot) -> None:
    global _bot
    _bot = bot


def crear_app():
    """App Flask minima con el panel, para pruebas y script manual."""
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = auth.clave_firma()
    app.register_blueprint(panel)
    return app


# ---------------------------------------------------------------------------
# Utilidades de sesion y permisos
# ---------------------------------------------------------------------------


def sesion_valida() -> dict | None:
    """Sesion vigente (dict) o None si no la hay o expiro."""
    if not session.get("discord_id"):
        return None
    creada = float(session.get("creada", 0) or 0)
    if time.time() - creada > DURACION_SESION:
        session.clear()
        return None
    return {
        "discord_id": session.get("discord_id"),
        "username": session.get("username", ""),
        "admin_guilds": list(session.get("admin_guilds", [])),
    }


def guilds_del_bot() -> list[int]:
    """Ids de servidores donde el bot esta conectado."""
    if _bot is None:
        return []
    presentes = []
    for guild in getattr(_bot, "guilds", []) or []:
        guild_id = getattr(guild, "id", None)
        if guild_id is not None:
            presentes.append(int(guild_id))
    return presentes


def servidores_administrados(sesion: dict) -> list[int]:
    """Interseccion: admin segun OAuth Y bot presente."""
    presentes = set(guilds_del_bot())
    return [g for g in sesion["admin_guilds"] if g in presentes]


def _origin_valido() -> bool:
    """Defensa CSRF ligera: el Origin (si viene) debe coincidir con el Host."""
    origin = request.headers.get("Origin", "")
    if not origin:
        return True
    return urllib.parse.urlparse(origin).netloc == request.host


def _escapar(texto) -> str:
    return html.escape(str(texto if texto is not None else ""), quote=True)


# ---------------------------------------------------------------------------
# Plantillas HTML (concatenacion sanitizada, sin emojis)
# ---------------------------------------------------------------------------


def _base(titulo: str, cuerpo: str) -> str:
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>" + _escapar(titulo) + "</title>"
        '<link rel="stylesheet" href="/panel/panel.css">'
        "</head><body>" + cuerpo + "</body></html>"
    )


def _pagina_login(url_discord: str) -> str:
    cuerpo = (
        '<div class="login-caja">'
        '<div class="marca">Panel del Bot</div>'
        '<p class="subtitulo">Configura tu servidor en un par de clicks. '
        "Acceso reservado a administradores.</p>"
        '<a class="enlace" href="/panel/login">'
        "<button type=\"button\">Iniciar sesion con Discord</button></a>"
        "</div>"
    )
    return _base("Panel - iniciar sesion", cuerpo)


def _pagina_panel(sesion: dict, guilds: list[int]) -> str:
    filas = ""
    for guild_id in guilds:
        filas = filas + (
            '<li><a href="/panel/servidor/' + str(int(guild_id)) + '">'
            "Servidor " + str(int(guild_id)) + "</a></li>"
        )
    if not filas:
        filas = (
            "<li>No administras ningun servidor donde el bot este presente.</li>"
        )
    cuerpo = (
        "<h1>Panel del Bot</h1>"
        '<p class="subtitulo">Sesion: ' + _escapar(sesion["username"]) + " - "
        '<a class="enlace" href="/panel/logout">Cerrar sesion</a></p>'
        '<div class="tarjeta"><h2>Tus servidores</h2>'
        '<ul class="lista-servidores">' + filas + "</ul></div>"
    )
    return _base("Panel - servidores", cuerpo)


def _campo_select(nombre: str, etiqueta: str, opciones: list, valor: str) -> str:
    inner = ""
    for opcion in opciones:
        marcado = " selected" if str(opcion) == str(valor) else ""
        inner = inner + '<option value="' + _escapar(opcion) + '"' + marcado + ">"
        inner = inner + _escapar(opcion) + "</option>"
    return (
        '<div class="campo"><label for="' + nombre + '">' + _escapar(etiqueta) + "</label>"
        '<select id="' + nombre + '" name="' + nombre + '">' + inner + "</select></div>"
    )


def _campo_numero(nombre: str, etiqueta: str, valor, minimo: int, maximo: int) -> str:
    return (
        '<div class="campo"><label for="' + nombre + '">' + _escapar(etiqueta) + "</label>"
        '<input type="number" id="' + nombre + '" name="' + nombre + '"'
        ' value="' + _escapar(valor) + '" min="' + str(minimo) + '" max="' + str(maximo) + '">'
        '<small class="error-campo" id="err-' + nombre + '"></small></div>'
    )


def _campo_texto(nombre: str, etiqueta: str, valor) -> str:
    return (
        '<div class="campo"><label for="' + nombre + '">' + _escapar(etiqueta) + "</label>"
        '<input type="text" id="' + nombre + '" name="' + nombre + '"'
        ' value="' + _escapar("" if valor is None else valor) + '"'
        ' placeholder="id o vacio para limpiar">'
        '<small class="error-campo" id="err-' + nombre + '"></small></div>'
    )


def _pagina_servidor(guild_id: int, datos: dict) -> str:
    eco = datos["economia"]
    gen = datos["general"]

    formulario = (
        '<form id="form-config" onsubmit="return false;">'
        '<div class="tarjeta"><h2>Economia y trabajos</h2><div class="grid-dos">'
        + _campo_select("work_mode", "Modo de trabajo", ["turnos", "cooldown"], eco["work_mode"])
        + _campo_select("minigame", "Minijuego", ["calculo", "memoria"], eco["minigame"])
        + _campo_numero("turns_per_session", "Turnos por sesion (1-5)", eco["turns_per_session"], 1, 5)
        + _campo_numero("sessions_per_day", "Sesiones por dia (1-10)", eco["sessions_per_day"], 1, 10)
        + _campo_numero("health_loss_chance", "Riesgo de salud por fallo % (0-100)", eco["health_loss_chance"], 0, 100)
        + _campo_numero("lucky_chance", "Entrada sin requisitos % (0-100)", eco["lucky_chance"], 0, 100)
        + "</div></div>"
        '<div class="tarjeta"><h2>Ajustes generales</h2><div class="grid-dos">'
        + _campo_texto("welcome_channel_id", "Canal de bienvenida", gen["welcome_channel_id"])
        + _campo_texto("ticket_category_id", "Categoria de tickets", gen["ticket_category_id"])
        + _campo_texto("alliance_channel_id", "Canal de alianzas", gen["alliance_channel_id"])
        + _campo_texto("hunter_role_id", "Rol cazador", gen["hunter_role_id"])
        + _campo_texto("alliance_role_id", "Rol alianza", gen["alliance_role_id"])
        + "</div>"
        '<div class="botonera"><button id="boton-guardar" type="button" onclick="guardar()">'
        "Guardar cambios</button>"
        '<span id="mensaje" class="mensaje"></span></div></div>'
        "</form>"
    )

    filas = ""
    for registro in reversed(datos["auditoria"]):
        filas = filas + (
            "<tr><td>" + _escapar(registro["campo"]) + "</td>"
            "<td>" + _escapar(registro["valor_anterior"]) + "</td>"
            "<td>" + _escapar(registro["valor_nuevo"]) + "</td>"
            "<td>" + _escapar(registro["actor_name"]) + "</td>"
            "<td>" + _escapar(registro["fecha"]) + "</td></tr>"
        )
    tabla = (
        '<div class="tarjeta"><h2>Auditoria de configuracion</h2>'
        '<table id="tabla-auditoria"><thead><tr>'
        "<th>Campo</th><th>Anterior</th><th>Nuevo</th><th>Autor</th><th>Fecha (UTC)</th>"
        "</tr></thead><tbody>" + filas + "</tbody></table></div>"
    )

    cuerpo = (
        "<h1>Servidor " + str(int(guild_id)) + "</h1>"
        '<p class="subtitulo"><a class="enlace" href="/panel">Volver a la lista</a></p>'
        + formulario
        + tabla
        + '<script src="/panel/panel.js"></script>'
    )
    return _base("Panel - servidor " + str(guild_id), cuerpo)


def _pagina_aviso(titulo: str, mensaje: str) -> str:
    cuerpo = (
        '<div class="login-caja"><div class="tarjeta"><h2>' + _escapar(titulo) + "</h2>"
        "<p>" + _escapar(mensaje) + "</p>"
        '<p><a class="enlace" href="/panel">Volver al panel</a></p></div></div>'
    )
    return _base(titulo, cuerpo)


# ---------------------------------------------------------------------------
# Rutas: paginas
# ---------------------------------------------------------------------------


@panel.route("/panel")
def panel_home():
    sesion = sesion_valida()
    if sesion is None:
        state = secrets.token_urlsafe(16)
        session["oauth_state"] = state
        return _pagina_login(auth.construir_url_autorizacion(state))
    return _pagina_panel(sesion, servidores_administrados(sesion))


@panel.route("/panel/login")
def panel_login():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    return redirect(auth.construir_url_autorizacion(state))


@panel.route("/panel/callback")
def panel_callback():
    state = request.args.get("state", "")
    esperado = session.get("oauth_state", "")
    if not state or not esperado or state != esperado:
        return _pagina_aviso(
            "Login cancelado",
            "La validacion de seguridad fallo (state distinto). Vuelve al panel"
            " e inicia sesion de nuevo.",
        ), 400

    code = request.args.get("code", "")
    if not code:
        return _pagina_aviso(
            "Login cancelado", "Discord no devolvio el codigo de autorizacion."
        ), 400

    try:
        token = auth.intercambiar_codigo(code)
        usuario, guilds = auth.obtener_usuario_y_guilds(token["access_token"])
    except Exception as e:
        # Detalle del tipo de error en pantalla: es la unica consola disponible
        # (mismo criterio que el visor de logs de webserver.py)
        return _pagina_aviso(
            "Login fallido",
            "No se pudo completar el login con Discord ("
            + type(e).__name__
            + "). Revisa DISCORD_CLIENT_ID/SECRET y DASHBOARD_PUBLIC_URL, e intenta de nuevo.",
        ), 502

    session.pop("oauth_state", None)
    try:
        session["discord_id"] = int(usuario.get("id"))
    except (TypeError, ValueError):
        return _pagina_aviso("Login fallido", "Respuesta inesperada de Discord."), 502
    session["username"] = str(usuario.get("username", ""))
    session["admin_guilds"] = auth.extraer_admin_guilds(guilds)
    session["creada"] = time.time()
    auth.guardar_cuenta(usuario)
    return redirect("/panel")


@panel.route("/panel/logout")
def panel_logout():
    session.clear()
    return redirect("/panel")


@panel.route("/panel/servidor/<int:guild_id>")
def panel_servidor(guild_id: int):
    sesion = sesion_valida()
    if sesion is None:
        return _pagina_aviso(
            "Acceso denegado", "Necesitas iniciar sesion con Discord para ver esta pagina."
        ), 401
    if guild_id not in servidores_administrados(sesion):
        return _pagina_aviso(
            "Acceso denegado",
            "No tienes permisos de administrador sobre este servidor (o el bot"
            " no esta presente en el).",
        ), 403
    return _pagina_servidor(guild_id, configurador.obtener_vista_config(guild_id))


@panel.route("/panel/panel.css")
def panel_css():
    contenido = (RAIZ / "web" / "panel.css").read_bytes()
    return Response(contenido, mimetype="text/css")


@panel.route("/panel/panel.js")
def panel_js():
    contenido = (RAIZ / "web" / "panel.js").read_bytes()
    return Response(contenido, mimetype="text/javascript")


# ---------------------------------------------------------------------------
# Rutas: API JSON
# ---------------------------------------------------------------------------


@panel.route("/panel/api/servidor/<int:guild_id>/config", methods=["POST"])
def api_guardar_config(guild_id: int):
    sesion = sesion_valida()
    if sesion is None:
        return jsonify({"ok": False, "error": "sesion requerida"}), 401
    if guild_id not in servidores_administrados(sesion):
        return jsonify({"ok": False, "error": "sin permisos sobre este servidor"}), 403
    if not _origin_valido():
        return jsonify({"ok": False, "error": "origen no permitido"}), 403
    if not request.is_json:
        return jsonify({"ok": False, "error": "se espera application/json"}), 415

    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict):
        return jsonify({"ok": False, "error": "cuerpo JSON invalido"}), 400

    try:
        resultado = configurador.guardar_config(
            guild_id, sesion["discord_id"], sesion["username"], cuerpo
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify(
        {
            "ok": True,
            "cambios": resultado["cambios"],
            "auditoria": resultado["auditoria"],
        }
    )


@panel.route("/panel/api/servidor/<int:guild_id>/auditoria")
def api_auditoria(guild_id: int):
    sesion = sesion_valida()
    if sesion is None:
        return jsonify({"ok": False, "error": "sesion requerida"}), 401
    if guild_id not in servidores_administrados(sesion):
        return jsonify({"ok": False, "error": "sin permisos sobre este servidor"}), 403
    return jsonify(servidor_repo.get_auditoria(guild_id))
