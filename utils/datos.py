"""Utilidades compartidas por varios cogs."""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = BASE_DIR / "datos"

PATH_TRABAJOS = DATOS_DIR / "trabajos.json"
PATH_ENFERMEDADES = DATOS_DIR / "enfermedades.json"


def cargar_json(path) -> dict | list:
    """Lee un JSON de datos/. Devuelve {} si no existe o está corrupto."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def obtener_trabajos() -> list[dict]:
    """Devuelve la lista de trabajos normalizada."""
    data = cargar_json(PATH_TRABAJOS)
    if isinstance(data, dict):
        return data.get("jobs", [])
    if isinstance(data, list):
        return data
    return []


def buscar_trabajo(nombre_o_slug: str) -> dict | None:
    """Busca un trabajo por slug o por nombre (sin distinguir mayúsculas)."""
    objetivo = nombre_o_slug.strip().lower()
    for job in obtener_trabajos():
        slug = str(job.get("slug", "")).lower()
        name = str(job.get("name", "")).lower()
        if objetivo == slug or objetivo == name:
            return job
    return None


def obtener_enfermedades() -> list[dict]:
    data = cargar_json(PATH_ENFERMEDADES)
    if isinstance(data, dict):
        return data.get("diseases", [])
    return []


def sueldo_base(job: dict) -> int:
    """Sueldo del trabajo; 0 si no está definido."""
    for clave in ("sueldo", "salary", "pay", "income", "wage"):
        valor = job.get(clave)
        if valor is not None:
            try:
                return int(valor)
            except (TypeError, ValueError):
                continue
    return 0


def experiencia_requerida(job: dict) -> int:
    try:
        return int(job.get("required_experience", 0))
    except (TypeError, ValueError):
        return 0
