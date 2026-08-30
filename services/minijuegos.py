"""Generadores de preguntas para los minijuegos de trabajo.

Los dos tipos (calculo y memoria) producen la misma estructura basica:
texto (enunciado), opciones (4) y correcta (indice 0..3); memoria agrega
la secuencia y la posicion pedida. El rng se inyecta para que todo sea
determinista en los tests. Los textos no llevan emojis.
"""

PALABRAS = (
    "sol", "luna", "estrella", "nube", "lluvia",
    "viento", "arbol", "rio", "piedra", "flor",
)

# Desviaciones posibles para los distractores numericos
DESVIOS = (-10, -5, -3, -2, -1, 1, 2, 3, 5, 10)


def _opciones_numericas(rng, resultado: int) -> tuple[list[str], int]:
    """4 opciones unicas con el resultado en una posicion aleatoria."""
    correcta = rng.randint(0, 3)
    distractores: list[int] = []
    while len(distractores) < 3:
        candidato = resultado + rng.choice(DESVIOS)
        if candidato != resultado and candidato not in distractores:
            distractores.append(candidato)
    opciones: list[str] = []
    idx = 0
    for i in range(4):
        if i == correcta:
            opciones.append(str(resultado))
        else:
            opciones.append(str(distractores[idx]))
            idx += 1
    return opciones, correcta


def generar_calculo(rng) -> dict:
    """Pregunta de calculo mental con 4 opciones de boton."""
    a = rng.randint(2, 30)
    b = rng.randint(2, 30)
    operador = rng.choice(("+", "-", "*"))
    if operador == "+":
        resultado = a + b
    elif operador == "-":
        resultado = a - b
    else:
        resultado = a * b
    texto = "Cuanto es " + str(a) + " " + operador + " " + str(b) + "?"
    opciones, correcta = _opciones_numericas(rng, resultado)
    return {"tipo": "calculo", "texto": texto, "opciones": opciones, "correcta": correcta}


def generar_memoria(rng) -> dict:
    """Secuencia de 5 palabras y pregunta por la palabra de una posicion."""
    secuencia = rng.sample(PALABRAS, 5)
    posicion = rng.randint(1, 5)  # 1-indexed para que lo lea una persona
    correcta_palabra = secuencia[posicion - 1]

    correcta = rng.randint(0, 3)
    candidatos = [p for p in PALABRAS if p != correcta_palabra]
    distractores = rng.sample(candidatos, 3)
    opciones: list[str] = []
    idx = 0
    for i in range(4):
        if i == correcta:
            opciones.append(correcta_palabra)
        else:
            opciones.append(distractores[idx])
            idx += 1

    texto = (
        "Recuerda la secuencia: " + ", ".join(secuencia) + ". "
        "Cual palabra estaba en la posicion " + str(posicion) + "?"
    )
    return {
        "tipo": "memoria",
        "texto": texto,
        "opciones": opciones,
        "correcta": correcta,
        "secuencia": secuencia,
        "posicion": posicion,
    }


def generar_pregunta(tipo: str, rng) -> dict:
    """Despacha la generacion por tipo de minijuego."""
    if tipo == "calculo":
        return generar_calculo(rng)
    if tipo == "memoria":
        return generar_memoria(rng)
    raise ValueError("Tipo de minijuego desconocido: " + str(tipo))
