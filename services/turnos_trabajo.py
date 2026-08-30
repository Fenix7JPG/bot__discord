"""Motor de turnos de trabajo estilo Nekotina (logica pura, sin Discord).

Las funciones reciben la config del servidor, el trabajo y un rng; devuelven
dicts simples y nunca tocan la base de datos ni Discord: eso lo hace el cog.
El gestor de sesiones guarda estado efimero en memoria (una sesion por
jugador, expira a los MINUTOS_SESION y se libera al finalizar).
"""

from datetime import datetime, timedelta, timezone

from services import minijuegos

BONUS_RACHA = 0.25      # 25% del sueldo extra si la sesion es perfecta
XP_PROPORCION = 0.20    # la sesion reparte el 20% del sueldo como XP
SALUD_PERDIDA = 10      # salud que se pierde al enfermarse por un fallo
MINUTOS_SESION = 3      # tiempo para responder toda la sesion


def hoy_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Calculos de pago (puros, cubiertos por tests/test_turnos.py)
# ---------------------------------------------------------------------------

def calcular_pago_turno(sueldo: int, turnos: int, aciertos_previos: int) -> int:
    """Parte del sueldo que paga este turno; el residuo del reparto va al ultimo."""
    if turnos <= 0:
        return 0
    base = sueldo // turnos
    if aciertos_previos == turnos - 1:
        return sueldo - base * (turnos - 1)
    return base


def calcular_bonus(aciertos: int, turnos: int, sueldo: int) -> int:
    """Bonus del 25% solo si todos los turnos fueron aciertos."""
    if turnos > 0 and aciertos == turnos:
        return int(sueldo * BONUS_RACHA)
    return 0


def calcular_xp(sueldo: int, turnos: int, aciertos_previos: int) -> int:
    """XP del turno: el 20% del sueldo repartido igual que el pago."""
    total_xp = int(sueldo * XP_PROPORCION)
    return calcular_pago_turno(total_xp, turnos, aciertos_previos)


def tiro_riesgo(config: dict, trabajo: dict, rng) -> bool:
    """True si el fallo de este turno enferma al jugador."""
    es_riesgoso = int(trabajo.get("es_riesgoso", 0) or 0)
    if not es_riesgoso:
        return False
    chance = int(config.get("health_loss_chance", 0) or 0)
    if chance <= 0:
        return False
    return rng.uniform(0, 100) < chance


def aplicar_enfermedad(salud: int, config: dict, trabajo: dict, rng) -> tuple[int, bool]:
    """Tira el riesgo y descuenta SALUD_PERDIDA si toca. (salud_nueva, enfermo)."""
    if tiro_riesgo(config, trabajo, rng):
        return max(0, salud - SALUD_PERDIDA), True
    return salud, False


# ---------------------------------------------------------------------------
# Sesiones de turnos
# ---------------------------------------------------------------------------

def sesiones_disponibles(jugador: dict | None, hoy: str | None = None,
                         sesiones_maximas: int = 2) -> int:
    """Cuantas sesiones le quedan al jugador hoy (dia UTC).

    Si el perfil guarda un dia distinto a hoy, el contador ya expiro.
    """
    if hoy is None:
        hoy = hoy_utc()
    if not jugador:
        return sesiones_maximas
    if jugador.get("dia_ultimo_trabajo") != hoy:
        return sesiones_maximas
    hechas = int(jugador.get("sesiones_hoy", 0) or 0)
    return max(0, sesiones_maximas - hechas)


def crear_sesion(config: dict, trabajo: dict, rng) -> dict:
    """Arma la sesion del jugador con la primera pregunta incluida."""
    turnos_totales = int(config.get("turns_per_session", 3) or 1)
    minijuego = str(config.get("minigame", "calculo"))
    return {
        "trabajo": str(trabajo.get("slug", "")),
        "nombre_trabajo": str(trabajo.get("name", "")),
        "sueldo": int(trabajo.get("sueldo", 0) or 0),
        "es_riesgoso": bool(int(trabajo.get("es_riesgoso", 0) or 0)),
        "minigame": minijuego,
        "turnos_totales": turnos_totales,
        "turno_actual": 1,
        "aciertos": 0,
        "pagado": 0,
        "xp_ganada": 0,
        "config": dict(config),
        "trabajo_datos": dict(trabajo),
        "expira": datetime.now(tz=timezone.utc) + timedelta(minutes=MINUTOS_SESION),
        "pregunta_actual": minijuegos.generar_pregunta(minijuego, rng),
    }


def responder_turno(sesion: dict, indice_elegido: int, config: dict, trabajo: dict, rng) -> dict:
    """Procesa la respuesta del turno actual y muta la sesion.

    Recibe config y trabajo del servidor/jugador por parametro (contrato);
    la sesion los guarda tambien para el gestor. Devuelve {acerto, pago,
    perdio_salud, final} y, si es el ultimo turno, agrega resumen.
    """
    pregunta = sesion["pregunta_actual"]
    acerto = indice_elegido == pregunta["correcta"]
    resultado: dict = {"acerto": acerto, "pago": 0, "perdio_salud": False, "final": False}

    if acerto:
        pago = calcular_pago_turno(
            sesion["sueldo"], sesion["turnos_totales"], sesion["aciertos"]
        )
        xp = calcular_xp(sesion["sueldo"], sesion["turnos_totales"], sesion["aciertos"])
        sesion["pagado"] += pago
        sesion["xp_ganada"] += xp
        sesion["aciertos"] += 1
        resultado["pago"] = pago
        resultado["xp"] = xp
    elif bool(int(trabajo.get("es_riesgoso", 0) or 0)):
        resultado["perdio_salud"] = tiro_riesgo(config, trabajo, rng)
        if resultado["perdio_salud"]:
            sesion["salud_perdida"] = sesion.get("salud_perdida", 0) + SALUD_PERDIDA

    sesion["turno_actual"] += 1
    if sesion["turno_actual"] > sesion["turnos_totales"]:
        bonus = calcular_bonus(
            sesion["aciertos"], sesion["turnos_totales"], sesion["sueldo"]
        )
        resultado["final"] = True
        resultado["resumen"] = {
            "aciertos": sesion["aciertos"],
            "turnos": sesion["turnos_totales"],
            "bonus": bonus,
            "total": sesion["pagado"] + bonus,
            "xp": sesion["xp_ganada"],
            "salud_perdida": sesion.get("salud_perdida", 0),
        }
    else:
        sesion["pregunta_actual"] = minijuegos.generar_pregunta(sesion["minigame"], rng)
    return resultado


class GestorSesiones:
    """Sesiones activas en memoria: una por jugador, con expiracion."""

    def __init__(self):
        self._sesiones: dict[int, dict] = {}

    def _vigente(self, sesion: dict | None) -> dict | None:
        if sesion is None:
            return None
        if datetime.now(tz=timezone.utc) >= sesion["expira"]:
            return None
        return sesion

    def crear(self, user_id: int, config: dict, trabajo: dict, rng) -> dict:
        """Crea (o reemplaza) la sesion del jugador."""
        sesion = crear_sesion(config, trabajo, rng)
        self._sesiones[user_id] = sesion
        return sesion

    def obtener(self, user_id: int) -> dict | None:
        """Sesion vigente del jugador; libera la expirada si la hubiera."""
        sesion = self._vigente(self._sesiones.get(user_id))
        if sesion is None and user_id in self._sesiones:
            del self._sesiones[user_id]
        return sesion

    def responder(self, user_id: int, indice: int, rng) -> dict | None:
        """Responde el turno actual; None si no hay sesion vigente."""
        sesion = self.obtener(user_id)
        if sesion is None:
            return None
        resultado = responder_turno(
            sesion, indice, sesion["config"], sesion["trabajo_datos"], rng
        )
        if resultado["final"]:
            del self._sesiones[user_id]
        return resultado

    def liberar(self, user_id: int) -> None:
        self._sesiones.pop(user_id, None)
