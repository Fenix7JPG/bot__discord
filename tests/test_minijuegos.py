"""Tests de los generadores de minijuegos (calculo y memoria).

Escritos primero (RED). Todo con rng inyectado para determinismo.
"""

import random

from services import minijuegos


class TestGenerarCalculo:
    def test_estructura_completa(self):
        rng = random.Random(7)
        pregunta = minijuegos.generar_calculo(rng)
        assert pregunta["tipo"] == "calculo"
        assert len(pregunta["opciones"]) == 4
        assert 0 <= pregunta["correcta"] < 4
        assert pregunta["texto"], "debe tener enunciado"
        for opcion in pregunta["opciones"]:
            assert isinstance(opcion, str)

    def test_la_correcta_esta_entre_las_opciones(self):
        rng = random.Random(123)
        for _ in range(30):
            pregunta = minijuegos.generar_calculo(rng)
            valor_correcto = pregunta["opciones"][pregunta["correcta"]]
        # la respuesta correcta es siempre un numero entero como texto
        assert valor_correcto.lstrip("-").isdigit()

    def test_determinismo_con_mismo_rng(self):
        a = minijuegos.generar_calculo(random.Random(42))
        b = minijuegos.generar_calculo(random.Random(42))
        assert a == b

    def test_variedad_de_preguntas(self):
        rng = random.Random(9)
        textos = {minijuegos.generar_calculo(rng)["texto"] for _ in range(40)}
        assert len(textos) > 5, "las preguntas de calculo deben variar"


class TestGenerarMemoria:
    def test_estructura_completa(self):
        rng = random.Random(3)
        pregunta = minijuegos.generar_memoria(rng)
        assert pregunta["tipo"] == "memoria"
        assert len(pregunta["secuencia"]) == 5
        assert len(pregunta["opciones"]) == 4
        assert 0 <= pregunta["correcta"] < 4
        assert pregunta["texto"], "debe tener enunciado"

    def test_la_correcta_salen_de_la_secuencia(self):
        rng = random.Random(11)
        for _ in range(20):
            pregunta = minijuegos.generar_memoria(rng)
            correcta = pregunta["opciones"][pregunta["correcta"]]
            assert correcta in pregunta["secuencia"]

    def test_determinismo_con_mismo_rng(self):
        a = minijuegos.generar_memoria(random.Random(5))
        b = minijuegos.generar_memoria(random.Random(5))
        assert a == b


def test_generar_pregunta_despacha_por_tipo():
    rng = random.Random(1)
    assert minijuegos.generar_pregunta("calculo", rng)["tipo"] == "calculo"
    assert minijuegos.generar_pregunta("memoria", rng)["tipo"] == "memoria"
    import pytest

    with pytest.raises(ValueError):
        minijuegos.generar_pregunta("ajedrez", random.Random(1))
