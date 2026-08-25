"""Tests del cog /blackjack: baraja fija para partidas deterministas."""

from unittest.mock import MagicMock

import pytest

import cogs.diversion.blackjack as modulo_bj
from cogs.diversion.blackjack import BlackJack, VistaBlackjack, valor_mano
from database import jugadores_repo
from tests.fakes import FabricaInteraccion

# Cartas con valores controlados para cada escenario
MAZO_NATURAL_GANA = ["A♠", "K♥", "5♦", "9♣"]
MAZO_NATURAL_EMPATE = ["A♠", "K♥", "A♦", "Q♣"]
MAZO_NORMAL = ["K♠", "7♥", "5♦", "3♣"]
APUESTA = 10


def _mazo(cartas):
    return list(cartas) + ["2♣"] * 20


@pytest.fixture()
def cog(db_local):
    return BlackJack(MagicMock())


@pytest.fixture()
def jugador_rico(db_local):
    jugadores_repo.crear_jugador(111)
    jugadores_repo.actualizar_campo(111, "dinero", 100)
    return 111


def _instalar_mazo(monkeypatch, cartas):
    monkeypatch.setattr(modulo_bj, "crear_mazo", lambda: _mazo(cartas))


def test_valor_mano_baja_ases():
    """Los Ases bajan de 11 a 1 para no pasarse de 21."""
    assert valor_mano(["A♠", "K♥"]) == 21
    assert valor_mano(["A♠", "A♦", "9♣"]) == 21
    assert valor_mano(["K♠", "5♥"]) == 15


async def test_blackjack_apuesta_no_positiva(cog):
    """Apuesta cero o negativa se rechaza antes de tocar la BD."""
    for mala in (0, -5):
        inter = FabricaInteraccion.interaccion(user_id=111)
        await FabricaInteraccion.invocar(cog, "blackjack", inter, apuesta=mala)
        assert "mayor que 0" in inter.response.mensajes[0]["content"]


async def test_blackjack_sin_perfil(cog):
    """Sin /jugar previo avisa efimero."""
    inter = FabricaInteraccion.interaccion(user_id=1)

    await FabricaInteraccion.invocar(cog, "blackjack", inter, apuesta=APUESTA)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "/jugar" in enviado["content"]


async def test_blackjack_dinero_insuficiente(cog, jugador_rico):
    """Con saldo menor que la apuesta no arranca la partida."""
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "blackjack", inter, apuesta=500)

    contenido = inter.response.mensajes[0]["content"]
    assert "suficiente dinero" in contenido
    assert "$100" in contenido
    assert jugadores_repo.get_jugador(111)["dinero"] == 100


async def test_blackjack_reparte_y_descuenta_apuesta(cog, jugador_rico, monkeypatch):
    """Partida normal: descuenta la apuesta y envia el embed inicial."""
    _instalar_mazo(monkeypatch, MAZO_NORMAL)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "blackjack", inter, apuesta=APUESTA)

    assert jugadores_repo.get_jugador(111)["dinero"] == 90
    enviado = inter.followup.mensajes[0]
    assert enviado["embed"] is not None
    assert "Apuesta $10" in enviado["embed"].title
    assert enviado["view"] is not None
    # El dealer solo muestra una carta al principio
    campo_dealer = enviado["embed"].fields[0]
    assert "🂠" in campo_dealer.value


async def test_blackjack_natural_pago_3_sobre_2(cog, jugador_rico, monkeypatch):
    """Blackjack natural contra dealer normal paga 1.5 veces la apuesta."""
    _instalar_mazo(monkeypatch, MAZO_NATURAL_GANA)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "blackjack", inter, apuesta=APUESTA)

    # 100 - 10 (apuesta) + 10 (devolucion) + 15 (ganancia 3:2)
    assert jugadores_repo.get_jugador(111)["dinero"] == 115
    nota = inter.followup.mensajes[0]["embed"].description
    assert "Blackjack natural" in nota


async def test_blackjack_natural_empatado_recupera_apuesta(cog, jugador_rico, monkeypatch):
    """Si el dealer tambien tiene 21 el jugador recupera su apuesta."""
    _instalar_mazo(monkeypatch, MAZO_NATURAL_EMPATE)
    inter = FabricaInteraccion.interaccion(user_id=111)

    await FabricaInteraccion.invocar(cog, "blackjack", inter, apuesta=APUESTA)

    assert jugadores_repo.get_jugador(111)["dinero"] == 100
    assert "Recuperas tu apuesta" in inter.followup.mensajes[0]["embed"].description


def test_vista_oculta_segunda_carta_del_dealer():
    """Sin revelar, el embed muestra solo la primera carta del dealer."""
    vista = VistaBlackjack(1, ["K♠"], ["5♦", "3♣"], [], APUESTA)

    embed = vista.construir_embed()

    assert "🂠" in embed.fields[0].value
    revelado = vista.construir_embed(revelar_dealer=True)
    assert "3♣" in revelado.fields[0].value


async def test_vista_pedir_carta_actualiza_total(cog, db_local):
    """Pedir carta suma al total y desactiva el boton Doblar."""
    jugadores_repo.crear_jugador(222)
    vista = VistaBlackjack(222, ["K♠", "5♥"], ["5♦", "3♣"], ["4♣", "2♣"], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=222)

    await vista.pedir.callback(inter)

    assert valor_mano(vista.mano_jugador) == 19
    edicion = inter.response.ediciones[0]
    assert "Has pedido carta" in edicion["embed"].description
    boton_doblar = vista._boton_doblar()
    assert boton_doblar.disabled is True


async def test_vista_pedir_y_pasarse_pierde_apuesta(cog, db_local):
    """Pasarse de 21 termina la mano sin devolver dinero."""
    jugadores_repo.crear_jugador(333)
    jugadores_repo.actualizar_campo(333, "dinero", 50)
    vista = VistaBlackjack(333, ["K♠", "Q♥"], ["5♦", "3♣"], ["10♦"], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=333)

    await vista.pedir.callback(inter)

    assert vista.terminado is True
    assert "Te pasaste" in inter.response.ediciones[0]["embed"].description
    assert jugadores_repo.get_jugador(333)["dinero"] == 50  # sin cambios
    assert all(child.disabled for child in vista.children)


async def test_vista_plantarse_gana_el_jugador(cog, db_local):
    """Plantarse con mejor mano que el dealer paga el doble de la apuesta."""
    jugadores_repo.crear_jugador(444)
    jugadores_repo.actualizar_campo(444, "dinero", 90)
    vista = VistaBlackjack(444, ["K♠", "9♥"], ["10♦", "7♣"], [], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=444)

    await vista.plantarse.callback(inter)

    assert vista.terminado is True
    nota = inter.response.ediciones[0]["embed"].description
    assert "Ganaste" in nota or "Ganas" in nota
    assert jugadores_repo.get_jugador(444)["dinero"] == 110  # 90 + 10x2


async def test_vista_plantarse_pierde_contra_dealer(cog, db_local):
    """El dealer mejor equipado gana: la apuesta ya estaba descontada."""
    jugadores_repo.crear_jugador(555)
    jugadores_repo.actualizar_campo(555, "dinero", 90)
    vista = VistaBlackjack(555, ["K♠", "8♥"], ["10♦", "9♣"], [], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=555)

    await vista.plantarse.callback(inter)

    assert "Perdiste" in inter.response.ediciones[0]["embed"].description
    assert jugadores_repo.get_jugador(555)["dinero"] == 90


async def test_vista_plantarse_empate_devuelve_apuesta(cog, db_local):
    """En empate se recupera exactamente lo apostado."""
    jugadores_repo.crear_jugador(666)
    jugadores_repo.actualizar_campo(666, "dinero", 90)
    vista = VistaBlackjack(666, ["K♠", "8♥"], ["10♦", "8♣"], [], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=666)

    await vista.plantarse.callback(inter)

    assert "Empate" in inter.response.ediciones[0]["embed"].description
    assert jugadores_repo.get_jugador(666)["dinero"] == 100


async def test_vista_plantarse_dealer_se_pasa(cog, db_local):
    """Dealer sobre 21 paga como victoria del jugador."""
    jugadores_repo.crear_jugador(777)
    jugadores_repo.actualizar_campo(777, "dinero", 90)
    # Dealer en 16 roba del mazo hasta 17+: el As (11) lo lleva a 17, no se pasa
    vista = VistaBlackjack(777, ["K♠", "9♥"], ["10♦", "6♣"], ["A♠"], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=777)

    await vista.plantarse.callback(inter)

    assert "Ganaste" in inter.response.ediciones[0]["embed"].description
    assert jugadores_repo.get_jugador(777)["dinero"] == 110


async def test_vista_doblar_sin_fondos_avisa(cog, db_local):
    """Doblar exige tener al menos la apuesta otra vez."""
    jugadores_repo.crear_jugador(888)
    jugadores_repo.actualizar_campo(888, "dinero", 5)
    vista = VistaBlackjack(888, ["K♠", "5♥"], ["5♦", "3♣"], ["6♦"], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=888)

    await vista.doblar.callback(inter)

    enviado = inter.response.mensajes[0]
    assert enviado["ephemeral"] is True
    assert "doblar" in enviado["content"].lower()
    assert vista.apuesta == APUESTA  # no cambio
    assert jugadores_repo.get_jugador(888)["dinero"] == 5


async def test_vista_doblar_duplica_y_resuelve(cog, db_local):
    """Doblar cobra otra apuesta, da una carta y resuelve contra el dealer."""
    jugadores_repo.crear_jugador(999)
    jugadores_repo.actualizar_campo(999, "dinero", 90)
    vista = VistaBlackjack(999, ["K♠", "5♥"], ["10♦", "7♣"], ["6♦"], APUESTA)
    inter = FabricaInteraccion.interaccion(user_id=999)

    await vista.doblar.callback(inter)

    assert vista.apuesta == 20
    assert valor_mano(vista.mano_jugador) == 21
    # 90 (inicial) - 10 (doblar cobra otra apuesta) + 40 (ganar 20x2) = 120
    assert jugadores_repo.get_jugador(999)["dinero"] == 120


async def test_vista_check_bloquea_a_otro_usuario(cog):
    """Solo el autor juega los botones."""
    vista = VistaBlackjack(111, ["K♠"], ["5♦", "3♣"], [], APUESTA)
    ajena = FabricaInteraccion.interaccion(user_id=42)

    assert await vista.interaction_check(ajena) is False
    assert ajena.response.mensajes[0]["ephemeral"] is True
