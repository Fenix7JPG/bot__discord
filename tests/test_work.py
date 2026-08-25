"""Tests del cog /work: pagos, cooldown de 24h y riesgo de enfermedad."""

import random as modulo_random
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import cogs.economia.work as modulo_work
from cogs.economia.work import Work
from database import jugadores_repo
from tests.fakes import FabricaInteraccion

SLUG_INICIAL = "recogedor-de-basura"  # sueldo 5, XP requerida 0


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
def jugador_con_trabajo(db_local):
    jugadores_repo.crear_jugador(111)
    jugadores_repo.actualizar_campo(111, "trabajo", SLUG_INICIAL)
    return 111


async def test_work_sin_perfil(cog):
    """Sin /jugar previo avisa con mensaje efimero."""
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert inter.response.mensajes[0]["ephemeral"] is True
    assert "/jugar" in inter.response.mensajes[0]["content"]


async def test_work_sin_trabajo_asignado(cog, db_local):
    """Con perfil pero sin trabajo manda a postularse."""
    jugadores_repo.crear_jugador(222)
    inter = FabricaInteraccion.interaccion(user_id=222)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert inter.response.mensajes[0]["ephemeral"] is True
    assert "postularse-trabajo" in inter.response.mensajes[0]["content"]


async def test_work_primer_pago_completo(cog, jugador_con_trabajo, monkeypatch):
    """Primer /work paga el sueldo completo y la XP del rango."""
    _random_guiado(monkeypatch, cola_randint=[9])  # xp base 9
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "Trabajaste como" in contenido
    assert "$5" in contenido  # sueldo 5 x uniform 1.0
    assert "9 XP" in contenido
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["dinero"] == 5
    assert perfil["experiencia"] == 9
    assert perfil["fecha_trabajo"] is not None


async def test_work_cooldown_cumplido_paga_otra_vez(cog, jugador_con_trabajo, monkeypatch):
    """Pasadas 24h vuelve a pagar completo y acumula."""
    jugadores_repo.actualizar_campo(111, "dinero", 10)
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=25))
    _random_guiado(monkeypatch, cola_randint=[6])
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert "Trabajaste como" in inter.response.mensajes[0]["content"]
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["dinero"] == 15


async def test_work_anticipado_sin_enfermarse(cog, jugador_con_trabajo, monkeypatch):
    """Antes de 24h el pago se reduce a la mitad y no enferma si sale alto el roll."""
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=2))
    _random_guiado(monkeypatch, cola_randint=[100, 8])  # roll 100 (sin riesgo), xp base 8
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "24 horas" in contenido or "cansancio" in contenido.lower()
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["dinero"] == 2  # sueldo 5 // 2
    assert perfil["experiencia"] == 4  # (8 + 0) // 2
    assert perfil["salud"] == 100
    assert perfil["enfermedad"] is None


async def test_work_anticipado_enfermarse(cog, jugador_con_trabajo, monkeypatch):
    """Con roll bajo el jugador enferma: pierde salud y anota la enfermedad."""
    enfermedades = modulo_work.datos.obtener_enfermedades()
    resfriado = next(e for e in enfermedades if e.get("slug") == "resfriado")
    jugadores_repo.actualizar_campo(111, "dinero", 100)
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=2))
    # roll 1 (enferma), gasto medico 0, xp base 5
    _random_guiado(monkeypatch, cola_randint=[1, 0, 5], choice_valor=resfriado)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    contenido = inter.response.mensajes[0]["content"]
    assert "Resfriado común" in contenido
    assert "salud" in contenido.lower()
    perfil = jugadores_repo.get_jugador(111)
    assert perfil["salud"] == 95  # 100 - health_loss 5
    assert perfil["enfermedad"] == "Resfriado común"
    assert perfil["dinero"] == 100  # gasto medico 0
    assert perfil["experiencia"] == 1  # max(1, (5+0)//4)


async def test_work_salud_no_baja_de_cero(cog, jugador_con_trabajo, monkeypatch):
    """La salud queda en 0 como minimo tras una enfermedad grave."""
    enfermedades = modulo_work.datos.obtener_enfermedades()
    peor = max(enfermedades, key=lambda e: int(e.get("health_loss", 0)))
    jugadores_repo.actualizar_campo(111, "salud", 3)
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=1))
    _random_guiado(monkeypatch, cola_randint=[1, 0, 5], choice_valor=peor)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert jugadores_repo.get_jugador(111)["salud"] == 0


async def test_work_enfermedad_vieja_se_limpia_al_trabajar(cog, jugador_con_trabajo, monkeypatch):
    """Una enfermedad con mas de 3 dias desaparece al trabajar bien."""
    jugadores_repo.actualizar_campo(111, "enfermedad", "Gripe")
    jugadores_repo.actualizar_campo(111, "fecha_enfermedad", _hace(days=5))
    _random_guiado(monkeypatch, cola_randint=[5])
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    perfil = jugadores_repo.get_jugador(111)
    assert perfil["enfermedad"] is None
    assert perfil["fecha_enfermedad"] is None


async def test_work_enfermedad_reciente_se_mantiene(cog, jugador_con_trabajo, monkeypatch):
    """Una enfermedad reciente sigue en el perfil despues de trabajar."""
    jugadores_repo.actualizar_campo(111, "enfermedad", "Gripe")
    jugadores_repo.actualizar_campo(111, "fecha_enfermedad", _hace(days=1))
    _random_guiado(monkeypatch, cola_randint=[5])

    await FabricaInteraccion.invocar(cog, "work", FabricaInteraccion.interaccion(user_id=111))

    perfil = jugadores_repo.get_jugador(111)
    assert perfil["enfermedad"] == "Gripe"


async def test_work_enfermarse_sin_catalogo_avisa(cog, jugador_con_trabajo, monkeypatch):
    """Si no hay enfermedades cargadas responde efimero pidiendo al admin."""
    monkeypatch.setattr(modulo_work.datos, "obtener_enfermedades", lambda: [])
    jugadores_repo.actualizar_campo(111, "fecha_trabajo", _hace(hours=1))
    _random_guiado(monkeypatch, cola_randint=[1])
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "work", inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "catálogo" in enviado["content"].lower() or "catalogo" in enviado["content"].lower()


async def test_work_trabajo_desaparecido_del_catalogo(cog, db_local, monkeypatch):
    """Sueldo de reserva si el trabajo guardado ya no esta en trabajos.json."""
    jugadores_repo.crear_jugador(333)
    jugadores_repo.actualizar_campo(333, "trabajo", "astronauta-fantasma")
    _random_guiado(monkeypatch, cola_randint=[7])
    inter = FabricaInteraccion.interaccion(user_id=333)

    await FabricaInteraccion.invocar(cog, "work", inter)

    assert "$50" in inter.response.mensajes[0]["content"]  # SUELDO_DE_RESERVA
    assert jugadores_repo.get_jugador(333)["dinero"] == 50
