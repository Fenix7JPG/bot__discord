"""Acceso a los catalogos del juego: trabajos y enfermedades.

Los datos viven en la base de datos (tablas trabajos y enfermedades, sembradas
por database.catalogos). Esta capa ofrece busquedas y normalizacion sobre
esos catalogos con cache en memoria.
"""

from database import catalogos


def obtener_trabajos() -> list[dict]:
    """Lista completa de trabajos desde la BD."""
    return catalogos.cargar_trabajos()


def obtener_enfermedades() -> list[dict]:
    """Lista completa de enfermedades desde la BD."""
    return catalogos.cargar_enfermedades()


def buscar_trabajo(nombre_o_slug: str) -> dict | None:
    """Busca un trabajo por slug o por nombre (sin distinguir mayusculas)."""
    objetivo = nombre_o_slug.strip().lower()
    for job in obtener_trabajos():
        slug = str(job.get("slug", "")).lower()
        name = str(job.get("name", "")).lower()
        if objetivo == slug or objetivo == name:
            return job
    return None


def sueldo_base(job: dict) -> int:
    """Sueldo del trabajo; 0 si no esta definido."""
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
