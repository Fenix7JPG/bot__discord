"""Catalogos de contenido (trabajos y enfermedades) sembrados en la BD.

Todo dato del juego vive en la base de datos. Estos catalogos son contenido
estatico que se siembra una sola vez (y se actualiza con upsert si cambia):

- TRABAJOS se genera desde legacy/Chambas.txt con las reglas de sueldo de
  legacy/info.txt: mediocre 5-100, bajo 100-150, medio 150-230, alto 230-500,
  reparto lineal dentro de cada nivel y deduplicado por slug.
- ENFERMEDADES esta embebido aqui porque el archivo original era incompleto.

poblar_catalogos() es idempotente: puede ejecutarse cuantas veces haga falta.
"""

import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CHAMBAS = RAIZ / "legacy" / "Chambas.txt"

# Rangos de sueldo por nivel segun legacy/info.txt
RANGOS_SUELDO = {
    "mediocre": (5, 100),
    "bajo": (100, 150),
    "medio": (150, 230),
    "alto": (230, 500),
}

EMOJI_POR_NIVEL = {"mediocre": "🧹", "bajo": "🔧", "medio": "👷", "alto": "💼"}

EMOJIS_CONOCIDOS = (
    "🗑️🍽️🌱🚴🧽🚗♻️🛒🛍️📦🚛🧹🔨🖼️🌐👞🎵🎨🏡🕯️🛏️🎥🎧🌲🪪🍾🏟️🏗️🍞🗞️🍔🍕📏🏹🔥🧰📻👓🏪🏙️"
    "🟥⛏️🚓🎖️⭐✈️🎼🧑‍🎤🎭👩‍🚒👨‍🏫🪖👨‍💻👨‍🍳🌮🥊📹🌊🦴💥💃🌟🥇🕶️💀💊🎬📈👑🏦"
)

ENFERMEDADES = [
    {"slug": "resfriado", "name": "Resfriado común", "severity": "bajo", "health_loss": 5, "duration_days": 2, "treatment_cost": 20, "description": "Molestias leves, baja energía. Se recupera rápido."},
    {"slug": "gripe", "name": "Gripe", "severity": "medio", "health_loss": 10, "duration_days": 3, "treatment_cost": 50, "description": "Fiebre y cansancio. Mejora al tratarse."},
    {"slug": "intoxicacion", "name": "Intoxicación alimentaria", "severity": "medio", "health_loss": 12, "duration_days": 2, "treatment_cost": 60, "description": "Dolor estomacal y deshidratación; requiere atención."},
    {"slug": "fiebre", "name": "Fiebre", "severity": "medio", "health_loss": 8, "duration_days": 2, "treatment_cost": 40, "description": "Temperatura alta; conviene reposo o tratamiento."},
    {"slug": "fatiga-severa", "name": "Fatiga severa", "severity": "medio", "health_loss": 7, "duration_days": 3, "treatment_cost": 35, "description": "Agotamiento por sobreesfuerzo; descansa o curate."},
    {"slug": "neumonia", "name": "Neumonía", "severity": "alto", "health_loss": 20, "duration_days": 5, "treatment_cost": 200, "description": "Complicación grave; tratamiento caro recomendado."},
    {"slug": "fractura", "name": "Fractura", "severity": "alto", "health_loss": 15, "duration_days": 7, "treatment_cost": 300, "description": "Lesión física que limita acciones; necesita reparación médica."},
    {"slug": "corte-infectado", "name": "Corte infectado", "severity": "medio", "health_loss": 9, "duration_days": 4, "treatment_cost": 80, "description": "Herida que se infectó; tratar pronto para evitar empeorar."},
    {"slug": "gastroenteritis", "name": "Gastroenteritis", "severity": "medio", "health_loss": 11, "duration_days": 3, "treatment_cost": 60, "description": "Vómitos y diarrea; reduce salud rápidamente si no se trata."},
    {"slug": "infeccion-seria", "name": "Infección seria", "severity": "alto", "health_loss": 18, "duration_days": 5, "treatment_cost": 220, "description": "Infección que requiere intervención médica urgente."},
]


def _limpiar_emoji(linea: str) -> str:
    texto = linea.strip().strip('",')
    texto = "".join(c for c in texto if c not in EMOJIS_CONOCIDOS)
    return texto.strip()


def _hacer_slug(nombre: str) -> str:
    texto = unicodedata.normalize("NFKD", nombre)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto.lower())
    return texto.strip("-")


def generar_trabajos_desde_chambas(ruta=RUTA_CHAMBAS) -> list[dict]:
    """Construye la lista de trabajos desde legacy/Chambas.txt."""
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines()

    niveles: dict[str, list] = {}
    actual = None
    vistos: set[str] = set()

    encabezados = ("mediocre", "bajo", "medio", "alto")
    for linea in lineas:
        encabezado = linea.strip().rstrip(":").strip().lower()
        if encabezado in encabezados:
            actual = encabezado
            niveles.setdefault(actual, [])
            continue
        if actual is None or not linea.strip():
            continue
        nombre = _limpiar_emoji(linea)
        if not nombre:
            continue
        clave = _hacer_slug(nombre)
        if clave in vistos:
            continue  # duplicado en el archivo original
        vistos.add(clave)
        niveles[actual].append(nombre)

    jobs = []
    for nivel, nombres in niveles.items():
        minimo, maximo = RANGOS_SUELDO[nivel]
        total = len(nombres)
        paso = (maximo - minimo) / max(1, total - 1)
        for i, nombre in enumerate(nombres):
            jobs.append(
                {
                    "slug": _hacer_slug(nombre),
                    "name": nombre,
                    "emoji": EMOJI_POR_NIVEL[nivel],
                    "level": nivel,
                    "required_experience": i * 2,
                    "sueldo": int(minimo + paso * i),
                }
            )
    return jobs


def poblar_catalogos():
    """Siembra o actualiza los catalogos en la base de datos activa."""
    from database.database import db

    trabajos = generar_trabajos_desde_chambas()

    with db.connect() as conn:
        for job in trabajos:
            conn.execute(
                """
                INSERT INTO trabajos (slug, name, emoji, level, required_experience, sueldo)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    emoji = excluded.emoji,
                    level = excluded.level,
                    required_experience = excluded.required_experience,
                    sueldo = excluded.sueldo
                """,
                (
                    job["slug"],
                    job["name"],
                    job["emoji"],
                    job["level"],
                    job["required_experience"],
                    job["sueldo"],
                ),
            )

        for enf in ENFERMEDADES:
            conn.execute(
                """
                INSERT INTO enfermedades (slug, name, severity, health_loss, duration_days, treatment_cost, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    severity = excluded.severity,
                    health_loss = excluded.health_loss,
                    duration_days = excluded.duration_days,
                    treatment_cost = excluded.treatment_cost,
                    description = excluded.description
                """,
                (
                    enf["slug"],
                    enf["name"],
                    enf["severity"],
                    enf["health_loss"],
                    enf["duration_days"],
                    enf["treatment_cost"],
                    enf["description"],
                ),
            )

    # El cache de lectura queda obsoleto tras sembrar
    limpiar_cache()


# ---------------------------------------------------------------------------
# Cache de lectura (evita consultar la BD en cada mensaje)
# ---------------------------------------------------------------------------

_trabajos_cache: list[dict] | None = None
_enfermedades_cache: list[dict] | None = None


def limpiar_cache():
    global _trabajos_cache, _enfermedades_cache
    _trabajos_cache = None
    _enfermedades_cache = None


def cargar_trabajos() -> list[dict]:
    """Lista de trabajos desde la BD (con cache)."""
    global _trabajos_cache
    if _trabajos_cache is not None:
        return _trabajos_cache
    from database.database import db

    with db.connect() as conn:
        conn.execute(
            "SELECT slug, name, emoji, level, required_experience, sueldo FROM trabajos"
        )
        _trabajos_cache = conn.fetchall()
    return _trabajos_cache


def cargar_enfermedades() -> list[dict]:
    """Lista de enfermedades desde la BD (con cache)."""
    global _enfermedades_cache
    if _enfermedades_cache is not None:
        return _enfermedades_cache
    from database.database import db

    with db.connect() as conn:
        conn.execute(
            """
            SELECT slug, name, severity, health_loss, duration_days, treatment_cost, description
            FROM enfermedades
            """
        )
        _enfermedades_cache = conn.fetchall()
    return _enfermedades_cache
