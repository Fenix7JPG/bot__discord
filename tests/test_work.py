"""Tests del cog /work: modo turnos (nuevo) y modo cooldown (historico)."""

import random as modulo_random
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import cogs.economia.work as modulo_work
from cogs.economia.work import Work
from database import jugadores_repo, servidor_repo
from tests.fakes import FabricaInteraccion

SLUG_INICIAL = "recogedor-de-basura"  # sueldo 5, XP requerida 0
GUILD_ID = 100


def _hace(**kwargs):
    """Fecha ISO de hace N horas/dias."""
    return (datetime.now(tz=timezone.utc) - timedelta(**kwargs)).isoformat()


def _random_guiado(monkeypatch, cola_randint=None, uniform_valor=1.0, choice_valor=None):
    """Deja el modulo random determinista para el escenario del test."""
    cola = list(cola_randint or [])

    def randint_falso(a, b):
        return cola.pop(0) if cola else b

    monkeypatch.setattr(modulo_random, "randint", randint_falso)
    monkeypatch.setattr(modulo_random, "uniform", lambda a, b: uniform_valor)
    if choice_valor is not None:
        monkeypatch.setattr(modulo_random, "choice", lambda seq: choice_valor)


@pytest.fixture()
def cog(db_local):
    return Work(MagicMock())


@pytest.fixture()
def servidor_cooldown(db_local):
    """Fuerza el modo historico en el servidor de prueba."""
    servidor_repo.set_economia(
        GUILD_ID, {"work_mode": "cooldown"}, actor_id=1, actor_name="setup"
    )


@pytest.fixture()
def jugador_con_trabajo(db_local):
    jugadores_repo.crear_jugador(111)
    jugadores_repo.actualizar_campo(111, "trabajo", SLUG_INICIAL)
    return 111


def _interaccion(user_id, con_guild=True):
    if con_guild:
        guild = FabricaInteraccion.servidor(guild_id=GUILD_ID)
    else:
        guild = None
    return FabricaInteraccion.interaccion(user_id=user_id, guild=guild)


def _ultima_vista(inter):
    """Devuelve la ultima vista enviada (respuesta o followup)."""
    for mensaje in reversed(inter.response.mensajes):
        if mensaje.get("view") is not None:
            return mensaje["view"]
    return None


# ===========================================================================
# Casos generales (independientes del modo)
# ===========================================================================


async def test_work_sin_perfil(cog):
    """Sin /jugar previo avisa con mensaje efimero."""
    inter = _interaccion(1)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert inter.response.mensajes[0]["ephemeral"] is True
    assert "/jugar" in inter.response.mensajes[0]["content"]


async def test_work_sin_trabajo_asignado(cog, db_local):
    """Con perfil pero sin trabajo manda a postularse."""
    jugadores_repo.crear_jugador(222)
    inter = _interaccion(222)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert inter.response.mensajes[0]["ephemeral"] is True
    assert "postularse-trabajo" in inter.response.mensajes[0]["content"]


async def test_work_sin_guild_usa_defaults(cog, db_local, monkeypatch):
    """Sin guild (DM) el modo default es turnos y no explota."""
    jugadores_repo.crear_jugador(223)
    jugadores_repo.actualizar_campo(223, "trabajo", SLUG_INICIAL)
    inter = _interaccion(223, con_guild=False)
    _random_guiado(monkeypatch, uniform_valor=0.5)

    await FabricaInteraccion.invocar(cog, "work", inter)

    mensajes = inter.response.mensajes
    assert mensajes and mensajes[0].get("view") is not None


# ===========================================================================
# Modo turnos (default, estilo Nekotina)
# ===========================================================================


async def test_turnos_primer_turno_envia_botones(cog, db_local, jugador_con_trabajo):
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    mensaje = inter.response.mensajes[0]
    assert mensaje["view"] is not None
    assert "Sesion de trabajo" in mensaje["content"]
    assert "turno 1 de 3" in mensaje["content"]
    # el contador diario se anota al iniciar
    jugador = jugadores_repo.get_jugador(111)
    assert jugador["sesiones_hoy"] == 1


async def test_turnos_flujo_completo_pagos(cog, db_local, jugador_con_trabajo, monkeypatch):
    """Responde la sesion entera: cada acierto suma y el final paga."""
    _random_guiado(monkeypatch, uniform_valor=0.5)  # riesgo siempre falla
    inter = _interaccion(111)
    await FabricaInteraccion.invocar(cog, "work", inter)

    vista = _ultima_vista(inter)
    # turno 1: presionar la correcta
    boton_correcto = siguiente_boton = None
    for hijo in vista.children:
        pass
    # buscamos el indice correcto leyendo la sesion del gestor
    sesion = cog.gestor.obtener(111)
    indice = sesion["pregunta_actual"]["correcta"]
    await _presionar(cog, inter, indice)

    # turno 2 y 3: correctos tambien (la sesion regenera preguntas)
    for _ in range(2):
        sesion = cog.gestor.obtener(111)
        indice = sesion["pregunta_actual"]["correcta"]
        await _presionar(cog, inter, indice)

    perfil = jugadores_repo.get_jugador(111)
    # sueldo 5: 1+1+3 (residuo al ultimo) + bonus 1 (25% de 5)
    assert perfil["dinero"] == 6
    assert perfil["experiencia"] == 1  # 20% de 5 = 1
    assert cog.gestor.obtener(111) is None  # sesion liberada


async def _presionar(cog, inter_original, indice):
    """Simula la presion del boton: edita sobre la interaccion original."""
    inter_presion = MagicMock()
    inter_presion.user = inter_original.user
    inter_presion.response = inter_original.response
    await cog.procesar_presion(inter_presion, indice)


async def test_turnos_fallo_con_riesgo_pierde_salud(cog, db_local, jugador_con_trabajo, monkeypatch):
    """Fallo en trabajo riesgoso con tirada desfavorable resta salud al cerrar."""
    _random_guiado(monkeypatch, uniform_valor=0.0)  # riesgo siempre acierta
    # trabajo medio: riesgoso, 3 turnos sugeridos
    jugadores_repo.actualizar_campo(111, "trabajo", "licenciado")
    inter = _interaccion(111)
    await FabricaInteraccion.invocar(cog, "work", inter)

    # fallar todos los turnos
    for _ in range(3):
        sesion = cog.gestor.obtener(111)
        indice = (sesion["pregunta_actual"]["correcta"] + 1) % 4
        await _presionar(cog, inter, indice)

    perfil = jugadores_repo.get_jugador(111)
    assert perfil["salud"] == 70  # 3 fallos x 10 de salud, riesgo 100%
    assert perfil["dinero"] == 0  # fallos no pagan


async def test_turnos_limite_diario(cog, db_local, jugador_con_trabajo):
    """Agotadas las sesiones del dia avisa el reinicio 00:00 UTC."""
    hoy = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    jugadores_repo.actualizar_campos(111, {"dia_ultimo_trabajo": hoy, "sesiones_hoy": 2})

    inter = _interaccion(111)
    await FabricaInteraccion.invocar(cog, "work", inter)

    mensaje = inter.response.mensajes[0]
    assert mensaje["ephemeral"] is True
    assert "limite" in mensaje["content"].lower()
    assert "00:00 UTC" in mensaje["content"]


async def test_turnos_trabajo_desaparecido_del_catalogo(cog, db_local, jugador_con_trabajo):
    """El aviso manda a postularse de nuevo y no abre sesion."""
    jugadores_repo.actualizar_campo(111, "trabajo", "astronauta-fantasma")
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    mensaje = inter.response.mensajes[0]
    assert mensaje["ephemeral"] is True
    assert "ya no existe" in mensaje["content"]
    assert cog.gestor.obtener(111) is None


async def test_turnos_tercero_no_puede_presionar(cog, db_local, jugador_con_trabajo):
    """Un usuario distinto al dueno recibe aviso efimero."""
    inter = _interaccion(111)
    await FabricaInteraccion.invocar(cog, "work", inter)
    vista = _ultima_vista(inter)

    tercero = FabricaInteraccion.interaccion(user_id=999)
    await vista.manejar_respuesta(tercero, 0)

    assert tercero.response.mensajes[0]["ephemeral"] is True
    assert "no es tuya" in tercero.response.mensajes[0]["content"]


async def test_turnos_expiracion_responde_aviso(cog, db_local, jugador_con_trabajo):
    """Si la sesion expiro entre presiones, se avisa y se libera."""
    inter = _interaccion(111)
    await FabricaInteraccion.invocar(cog, "work", inter)

    sesion = cog.gestor.obtener(111)
    sesion["expira"] = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    await _presionar(cog, inter, 0)

    contenido = inter.response.ediciones[-1]["content"]
    assert "expirada" in contenido.lower()


# ===========================================================================
# Modo cooldown clasico (historico, se conserva con config explicita)
# ===========================================================================


async def test_cooldown_primer_pago_completo(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """Primer /work paga el sueldo completo y la XP del rango."""
    _random_guiado(monkeypatch, cola_randint=[9])  # xp base 9
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "Trabajaste como" in contenido
    assert "$5" in contenido  # sueldo 5 x uniform 1.0
    assert "9 XP" in contenido
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["dinero"] == 5
    assert perfil["experiencia"] == 9
    assert perfil["fecha_trabajo"] is not None


async def test_cooldown_cumplido_paga_otra_vez(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """Pasadas 24h vuelve a pagar completo y acumula."""
    jugadores_repo.actualizar_campo(111, "dinero", 10)
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=25))
    _random_guiado(monkeypatch, cola_randint=[6])
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert "Trabajaste como" in inter.response.mensajes[0]["content"]
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["dinero"] == 15


async def test_cooldown_anticipado_sin_enfermarse(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """Antes de 24h el pago se reduce a la mitad y no enferma si sale alto el roll."""
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=2))
    _random_guiado(monkeypatch, cola_randint=[100, 8])  # roll 100 (sin riesgo), xp base 8
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "24 horas" in contenido or "cansancio" in contenido.lower()
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["dinero"] == 2  # sueldo 5 // 2
    assert perfil["experiencia"] == 4  # (8 + 0) // 2
    assert perfil["salud"] == 100
    assert perfil["enfermedad"] is None


async def test_cooldown_anticipado_enfermarse(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """Con roll bajo el jugador enferma: pierde salud y anota la enfermedad."""
    enfermedades = modulo_work.datos.obtener_enfermedades()
    resfriado = next(e for e in enfermedades if e.get("slug") == "resfriado")
    jugadores_repo.actualizar_campo(111, "dinero", 100)
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=2))
    # roll 1 (enferma), gasto medico 0, xp base 5
    _random_guiado(monkeypatch, cola_randint=[1, 0, 5], choice_valor=resfriado)
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "Resfriado común" in contenido
    assert "salud" in contenido.lower()
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["salud"] == 95  # 100 - health_loss 5
    assert perfil["enfermedad"] == "Resfriado común"
    assert perfil["dinero"] == 100  # gasto medico 0
    assert perfil["experiencia"] == 1  # max(1, (5+0)//4)


async def test_cooldown_salud_no_baja_de_cero(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """La salud queda en 0 como minimo tras una enfermedad grave."""
    enfermedades = modulo_work.datos.obtener_enfermedades()
    peor = max(enfermedades, key=lambda e: int(e.get("health_loss", 0)))
    jugadores_repo.actualizar_campo(111, "salud", 3)
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=1))
    _random_guiado(monkeypatch, cola_randint=[1, 0, 5], choice_valor=peor)
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert jugadores_repo.get_jugador(111)["salud"] == 0


async def test_cooldown_enfermedad_vieja_se_limpia_al_trabajar(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """Una enfermedad con mas de 3 dias desaparece al trabajar bien."""
    jugadores_repo.actualizar_campo(111, "enfermedad", "Gripe")
    jugadores_repo.actualizar_campo(111, "fecha_enfermedad", _hace(days=5))
    _random_guiado(monkeypatch, cola_randint=[5])
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    perfil = jugadores_repo.get_jugador(111)
    assert perfil["enfermedad"] is None
    assert perfil["fecha_enfermedad"] is None


async def test_cooldown_enfermedad_reciente_se_mantiene(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """Una enfermedad reciente sigue en el perfil despues de trabajar."""
    jugadores_repo.actualizar_campo(111, "enfermedad", "Gripe")
    jugadores_repo.actualizar_campo(111, "fecha_enfermedad", _hace(days=1))
    _random_guiado(monkeypatch, cola_randint=[5])

    await FabricaInteraccion.invocar(cog, "work", _interaccion(111))

    perfil = jugadores_repo.get_jugador(111)
    assert perfil["enfermedad"] == "Gripe"


async def test_cooldown_enfermarse_sin_catalogo_avisa(cog, servidor_cooldown, jugador_con_trabajo, monkeypatch):
    """Si no hay enfermedades cargadas responde efimero pidiendo al admin."""
    monkeypatch.setattr(modulo_work.datos, "obtener_enfermedades", lambda: [])
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=1))
    _random_guiado(monkeypatch, cola_randint=[1])
    inter = _interaccion(111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "catálogo" in enviado["content"].lower() or "catalogo" in enviado["content"].lower()


async def test_cooldown_trabajo_desaparecido_del_catalogo(cog, servidor_cooldown, db_local, monkeypatch):
    """Sueldo de reserva si el trabajo guardado ya no esta en el catalogo."""
    jugadores_repo.crear_jugador(333)
    jugadores_repo.actualizar_campo(333, "trabajo", "astronauta-fantasma")
    _random_guiado(monkeypatch, cola_randint=[7])
    inter = _interaccion(333)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert "$50" in inter.response.mensajes[0]["content"]  # SUELDO_DE_RESERVA
    assert jugadores_repo.get_jugador(333)["dinero"] == 50
