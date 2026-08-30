"""Tests del motor de turnos de trabajo (logica pura, sin Discord).

Escritos primero (RED). Pagos, limites diarios, riesgo y GestorSesiones.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest

from services import turnos_trabajo as turnos


CONFIG_BASE = {
    "work_mode": "turnos",
    "minigame": "calculo",
    "turns_per_session": 3,
    "sessions_per_day": 2,
    "health_loss_chance": 35,
    "lucky_chance": 30,
}

TRABAJO = {
    "slug": "carpintero",
    "name": "Carpintero",
    "sueldo": 120,
    "level": "medio",
    "turnos_sugeridos": 3,
    "es_riesgoso": 1,
    "required_experience": 10,
}


class TestCalcularPago:
    def test_pago_por_turno_reparte_el_sueldo(self):
        # 120 repartido en 3 turnos = 40 por acierto
        assert turnos.calcular_pago_turno(120, 3, aciertos_previos=0) == 40
        assert turnos.calcular_pago_turno(120, 3, aciertos_previos=2) == 40

    def test_reparto_con_redondeo_no_pierde_dinero(self):
        # 100 en 3 turnos: 33+33+33 = 99; el residuo va al ultimo turno
        assert turnos.calcular_pago_turno(100, 3, aciertos_previos=0) == 33
        assert turnos.calcular_pago_turno(100, 3, aciertos_previos=2) == 34

    def test_bonus_solo_racha_perfecta(self):
        assert turnos.calcular_bonus(aciertos=3, turnos=3, sueldo=120) == 30
        assert turnos.calcular_bonus(aciertos=2, turnos=3, sueldo=120) == 0

    def test_calculo_xp_proporcional(self):
        # XP = 20% del sueldo repartida igual que el pago
        total = 0
        for aciertos_previos in range(3):
            total += turnos.calcular_xp(120, 3, aciertos_previos)
        assert total == 24  # 20% de 120


class TestCrearSesion:
    def test_sesion_inicial(self):
        rng = random.Random(4)
        sesion = turnos.crear_sesion(CONFIG_BASE, TRABAJO, rng)
        assert sesion["trabajo"] == "carpintero"
        assert sesion["turnos_totales"] == 3
        assert sesion["turno_actual"] == 1
        assert sesion["aciertos"] == 0
        assert sesion["pagado"] == 0
        assert sesion["xp_ganada"] == 0
        assert sesion["pregunta_actual"]["tipo"] == "calculo"
        assert "expira" in sesion


class TestResponderTurno:
    def test_acierto_paga_y_suma_xp(self):
        rng = random.Random(4)
        sesion = turnos.crear_sesion(CONFIG_BASE, TRABAJO, rng)
        correcta = sesion["pregunta_actual"]["correcta"]
        resultado = turnos.responder_turno(sesion, correcta, CONFIG_BASE, TRABAJO, rng)
        assert resultado["acerto"] is True
        assert resultado["pago"] == 40
        assert sesion["pagado"] == 40
        assert sesion["aciertos"] == 1
        assert sesion["xp_ganada"] == 8

    def test_fallo_paga_cero_y_avanza(self):
        rng = random.Random(4)
        sesion = turnos.crear_sesion(CONFIG_BASE, TRABAJO, rng)
        incorrecta = (sesion["pregunta_actual"]["correcta"] + 1) % 4
        resultado = turnos.responder_turno(sesion, incorrecta, CONFIG_BASE, TRABAJO, rng)
        assert resultado["acerto"] is False
        assert resultado["pago"] == 0
        assert sesion["aciertos"] == 0
        assert sesion["turno_actual"] == 2

    def test_ultimo_turno_devuelve_resumen_con_bonus(self):
        rng = random.Random(4)
        sesion = turnos.crear_sesion(CONFIG_BASE, TRABAJO, rng)
        total_pago = 0
        for _ in range(3):
            correcta = sesion["pregunta_actual"]["correcta"]
            resultado = turnos.responder_turno(sesion, correcta, CONFIG_BASE, TRABAJO, rng)
            total_pago += resultado["pago"]
        assert resultado["final"] is True
        assert resultado["resumen"]["bonus"] == 30  # 25% de 120
        assert resultado["resumen"]["total"] == total_pago + 30
        assert resultado["resumen"]["aciertos"] == 3

    def test_sesion_no_reinicia_la_misma_pregunta(self):
        rng = random.Random(4)
        sesion = turnos.crear_sesion(CONFIG_BASE, TRABAJO, rng)
        primera = sesion["pregunta_actual"]["texto"]
        correcta = sesion["pregunta_actual"]["correcta"]
        resultado = turnos.responder_turno(sesion, correcta, CONFIG_BASE, TRABAJO, rng)
        assert resultado["final"] is False
        assert sesion["pregunta_actual"]["texto"] != primera or sesion["turno_actual"] == 2


class TestRiesgo:
    def test_riesgo_con_rng_favorable_no_enferma(self):
        # Random(2).uniform(0,100) = 95.6 >= 35: la tirada cae fuera del 35% de riesgo
        rng = random.Random(2)
        salud, enfermo = turnos.aplicar_enfermedad(100, CONFIG_BASE, TRABAJO, rng)
        assert enfermo is False
        assert salud == 100

    def test_riesgo_con_rng_desfavorable_enferma(self):
        # Random(1).uniform(0,100) = 13.44 < 35: cae dentro del 35% de riesgo
        rng = random.Random(1)
        salud, enfermo = turnos.aplicar_enfermedad(100, CONFIG_BASE, TRABAJO, rng)
        assert enfermo is True
        assert salud == 90  # pierde 10 de salud

    def test_determinismo_con_mismo_rng(self):
        for semilla in (3, 7, 11):
            a = turnos.aplicar_enfermedad(100, CONFIG_BASE, TRABAJO, random.Random(semilla))
            b = turnos.aplicar_enfermedad(100, CONFIG_BASE, TRABAJO, random.Random(semilla))
            assert a == b

    def test_trabajo_no_riesgoso_nunca_enferma(self):
        trabajo_seguro = dict(TRABAJO, es_riesgoso=0)
        for semilla in range(20):
            rng = random.Random(semilla)
            _, enfermo = turnos.aplicar_enfermedad(100, CONFIG_BASE, trabajo_seguro, rng)
            assert enfermo is False

    def test_riesgo_cero_nunca_enferma(self):
        config = dict(CONFIG_BASE, health_loss_chance=0)
        for semilla in range(20):
            _, enfermo = turnos.aplicar_enfermedad(100, config, TRABAJO, random.Random(semilla))
            assert enfermo is False

    def test_no_baja_de_cero_de_salud(self):
        config = dict(CONFIG_BASE, health_loss_chance=100)
        salud, enfermo = turnos.aplicar_enfermedad(5, config, TRABAJO, random.Random(1))
        assert enfermo is True
        assert salud == 0


class TestSesionesDisponibles:
    def test_sin_historial_hay_todas(self):
        assert turnos.sesiones_disponibles(None, "2026-08-30") == 2

    def test_mismo_dia_descuenta(self):
        jugador = {"dia_ultimo_trabajo": "2026-08-30", "sesiones_hoy": 1}
        assert turnos.sesiones_disponibles(jugador, "2026-08-30") == 1

    def test_dia_distinto_resetea(self):
        jugador = {"dia_ultimo_trabajo": "2026-08-29", "sesiones_hoy": 2}
        assert turnos.sesiones_disponibles(jugador, "2026-08-30") == 2

    def test_hoy_levanta_el_dia_utc(self):
        hoy = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        jugador = {"dia_ultimo_trabajo": hoy, "sesiones_hoy": 2}
        assert turnos.sesiones_disponibles(jugador) == 0


class TestGestorSesiones:
    def test_crear_y_obtener(self):
        gestor = turnos.GestorSesiones()
        rng = random.Random(4)
        sesion = gestor.crear(user_id=1, config=CONFIG_BASE, trabajo=TRABAJO, rng=rng)
        assert gestor.obtener(1) is sesion

    def test_una_sola_sesion_por_usuario(self):
        gestor = turnos.GestorSesiones()
        rng = random.Random(4)
        gestor.crear(user_id=1, config=CONFIG_BASE, trabajo=TRABAJO, rng=rng)
        segunda = gestor.crear(user_id=1, config=CONFIG_BASE, trabajo=TRABAJO, rng=rng)
        assert gestor.obtener(1) is segunda

    def test_expiracion_tres_minutos(self):
        gestor = turnos.GestorSesiones()
        rng = random.Random(4)
        sesion = gestor.crear(user_id=1, config=CONFIG_BASE, trabajo=TRABAJO, rng=rng)
        # simular que pasaron mas de 3 minutos
        sesion["expira"] = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
        assert gestor.obtener(1) is None, "la sesion expirada se libera"
        # y se puede crear una nueva
        nueva = gestor.crear(user_id=1, config=CONFIG_BASE, trabajo=TRABAJO, rng=rng)
        assert gestor.obtener(1) is nueva

    def test_responder_y_finalizar_libera(self):
        gestor = turnos.GestorSesiones()
        rng = random.Random(4)
        config = dict(CONFIG_BASE, turns_per_session=1)
        gestor.crear(user_id=1, config=config, trabajo=TRABAJO, rng=rng)
        gestor.responder(user_id=1, indice=0, rng=rng)
        assert gestor.obtener(1) is None, "al finalizar la sesion se libera"
