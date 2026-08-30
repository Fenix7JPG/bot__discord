"""Tests de configuracion de economia por servidor, auditoria y campos nuevos.

Estos tests se escribieron PRIMERO (RED) antes que la implementacion de
servidor_repo.get_economia/set_economia (constitution: test-first).
"""

from datetime import datetime, timezone

import pytest

from database import jugadores_repo, servidor_repo


DEFAULTS_ESPERADOS = {
    "work_mode": "turnos",
    "minigame": "calculo",
    "turns_per_session": 3,
    "sessions_per_day": 2,
    "health_loss_chance": 35,
    "lucky_chance": 30,
}


def test_get_economia_devuelve_defaults_sin_fila(db_local):
    config = servidor_repo.get_economia(guild_id=100)
    for campo, esperado in DEFAULTS_ESPERADOS.items():
        assert config[campo] == esperado, "default de " + campo + " incorrecto"


def test_get_economia_con_fila_gurada(db_local):
    servidor_repo.set_economia(
        100, {"turns_per_session": 5}, actor_id=1, actor_name="tester"
    )
    config = servidor_repo.get_economia(100)
    assert config["turns_per_session"] == 5
    # los demas campos conservan defaults
    assert config["sessions_per_day"] == DEFAULTS_ESPERADOS["sessions_per_day"]


def test_set_economia_upsert_reiterado(db_local):
    servidor_repo.set_economia(100, {"turns_per_session": 5}, actor_id=1, actor_name="t")
    servidor_repo.set_economia(100, {"turns_per_session": 4}, actor_id=1, actor_name="t")
    config = servidor_repo.get_economia(100)
    assert config["turns_per_session"] == 4


@pytest.mark.parametrize("campo,invalido", [
    ("turns_per_session", 0),
    ("turns_per_session", 6),
    ("sessions_per_day", 0),
    ("sessions_per_day", 11),
    ("health_loss_chance", -1),
    ("health_loss_chance", 101),
    ("lucky_chance", -1),
    ("lucky_chance", 101),
])
def test_set_economia_rechaza_fuera_de_rango(db_local, campo, invalido):
    with pytest.raises(ValueError):
        servidor_repo.set_economia(100, {campo: invalido}, actor_id=1, actor_name="t")


def test_set_economia_rechaza_enum_invalido(db_local):
    with pytest.raises(ValueError):
        servidor_repo.set_economia(100, {"work_mode": "caos"}, actor_id=1, actor_name="t")
    with pytest.raises(ValueError):
        servidor_repo.set_economia(100, {"minigame": "ajedrez"}, actor_id=1, actor_name="t")


def test_set_economia_no_escribe_parcial(db_local):
    # Guardado valido inicial
    servidor_repo.set_economia(100, {"turns_per_session": 2}, actor_id=1, actor_name="t")
    # Intento con un campo valido y otro invalido: se rechaza TODO
    with pytest.raises(ValueError):
        servidor_repo.set_economia(
            100, {"turns_per_session": 4, "sessions_per_day": 99},
            actor_id=1, actor_name="t",
        )
    config = servidor_repo.get_economia(100)
    assert config["turns_per_session"] == 2, "no debe escribir si otro campo es invalido"


def test_auditoria_registra_cambios(db_local):
    cambios = servidor_repo.set_economia(
        100,
        {"turns_per_session": 5, "health_loss_chance": 10},
        actor_id=42,
        actor_name="Admin Prueba",
    )
    campos_cambiados = sorted(c["campo"] for c in cambios)
    assert campos_cambiados == ["health_loss_chance", "turns_per_session"]

    registros = servidor_repo.get_auditoria(100)
    assert len(registros) == 2
    por_campo = {r["campo"]: r for r in registros}
    tp = por_campo["turns_per_session"]
    assert tp["valor_anterior"] == "3"
    assert tp["valor_nuevo"] == "5"
    assert tp["actor_id"] == 42
    assert tp["actor_name"] == "Admin Prueba"
    fecha = datetime.fromisoformat(tp["fecha"])
    assert fecha.tzinfo is not None, "la fecha debe ser ISO con zona (UTC)"
    assert fecha.tzinfo == timezone.utc or fecha.utcoffset() is not None


def test_auditoria_no_registra_sin_cambio(db_local):
    servidor_repo.set_economia(100, {"turns_per_session": 3}, actor_id=1, actor_name="t")
    assert servidor_repo.get_auditoria(100) == [], "valor igual al default no es cambio"


def test_auditoria_limit(db_local):
    for valor in (1, 2, 3, 4, 5):
        servidor_repo.set_economia(
            100, {"turns_per_session": valor}, actor_id=1, actor_name="t"
        )
    registros = servidor_repo.get_auditoria(100, limit=3)
    assert len(registros) == 3


def test_jugadores_acepta_campos_nuevos(db_local):
    jugadores_repo.crear_jugador(42)
    jugadores_repo.actualizar_campo(42, "dia_ultimo_trabajo", "2026-08-30")
    jugadores_repo.actualizar_campo(42, "sesiones_hoy", 2)
    jugador = jugadores_repo.get_jugador(42)
    assert jugador["dia_ultimo_trabajo"] == "2026-08-30"
    assert jugador["sesiones_hoy"] == 2


def test_setup_idempotente(db_local):
    # db.setup() ya corrio en el fixture; correrlo de nuevo no debe fallar
    from database.database import db

    db.setup()
    db.setup()
