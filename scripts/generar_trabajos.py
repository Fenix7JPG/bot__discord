"""Genera datos/trabajos.json a partir de legacy/Chambas.txt y legacy/info.txt.

Reglas (según info.txt):
    mediocre 5-100, bajo 100-150, medio 150-230, alto 230-500.
El sueldo se reparte linealmente dentro del rango del nivel según la posición
del trabajo en su lista. Los duplicados (mismo nombre normalizado) se omiten.

Uso: python scripts/generar_trabajos.py
"""

import json
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CHAMBAS = BASE_DIR / "legacy" / "Chambas.txt"
SALIDA = BASE_DIR / "datos" / "trabajos.json"

# Rangos de sueldo por nivel, tal como los define legacy/info.txt
RANGOS = {
    "mediocre": (5, 100),
    "bajo": (100, 150),
    "medio": (150, 230),
    "alto": (230, 500),
}

# Encabezados del archivo de chambas -> clave de nivel
ENCABEZADOS = {
    "mediocre": "mediocre",
    "bajo": "bajo",
    "medio": "medio",
    "alto": "alto",
}

EMOJIS_CONOCIDOS = (
    "🗑️🍽️🌱🚴🧽🚗♻️🛒🛍️📦🚛🧹🔨🖼️🌐👞🎵🎨🏡🕯️🛏️🎥🎧🌲🪪🍾🏟️🏗️🍞🗞️🍔🍕📏🏹🔥🧰📻👓🏪🏙️"
    "🟥⛏️🚓🎖️⭐✈️🎼🧑‍🎤🎭👩‍🚒👨‍🏫🪖👨‍💻👨‍🍳🌮🥊📹🌊🦴💥💃🌟🥇🕶️💀💊🎬📈👑🏦"
)


def limpiar_emoji(linea: str) -> str:
    """Quita comillas, emojis y espacios sobrantes de una línea."""
    texto = linea.strip().strip('",')
    texto = "".join(c for c in texto if c not in EMOJIS_CONOCIDOS)
    return texto.strip()


def hacer_slug(nombre: str) -> str:
    """Nombre a slug: sin acentos, minúsculas, guiones."""
    texto = unicodedata.normalize("NFKD", nombre)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto.lower())
    return texto.strip("-")


def main():
    lineas = CHAMBAS.read_text(encoding="utf-8").splitlines()

    niveles = {}   # nivel -> [nombres]
    actual = None
    vistos = set()

    for linea in lineas:
        encabezado = linea.strip().rstrip(":").strip().lower()
        if encabezado in ENCABEZADOS:
            actual = ENCABEZADOS[encabezado]
            niveles.setdefault(actual, [])
            continue
        if actual is None or not linea.strip():
            continue
        nombre = limpiar_emoji(linea)
        if not nombre:
            continue
        clave = hacer_slug(nombre)
        if clave in vistos:
            continue  # dedupe
        vistos.add(clave)
        niveles[actual].append(nombre)

    # Emoji genérico por nivel (los del txt eran inconsistentes)
    emoji_nivel = {"mediocre": "🧹", "bajo": "🔧", "medio": "👷", "alto": "💼"}

    jobs = []
    for nivel, nombres in niveles.items():
        minimo, maximo = RANGOS[nivel]
        total = len(nombres)
        for i, nombre in enumerate(nombres):
            # Sueldo lineal dentro del rango del nivel
            paso = (maximo - minimo) / max(1, total - 1)
            sueldo = int(minimo + paso * i)
            jobs.append(
                {
                    "slug": hacer_slug(nombre),
                    "name": nombre,
                    "emoji": emoji_nivel[nivel],
                    "level": nivel,
                    "required_experience": i * 2,  # progresión suave dentro del nivel
                    "sueldo": sueldo,
                }
            )

    SALIDA.parent.mkdir(exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({"jobs": jobs}, f, ensure_ascii=False, indent=2)

    print("Trabajos generados:", len(jobs))
    for nivel, nombres in niveles.items():
        print(" ", nivel, "->", len(nombres))


if __name__ == "__main__":
    main()
