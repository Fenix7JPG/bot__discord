"""Migración de datos.json (perfiles JSON antiguos) a la tabla jugadores.

Uso:
    python scripts/migrar_json_a_db.py [ruta_data_json]

Si no se pasa ruta, usa legacy/data.json. Es idempotente: los usuarios que ya
existen en la base se omiten. Funciona contra la BD configurada en el entorno
(local o Turso).
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database.database import db  # noqa: E402


def migrar(ruta: Path) -> None:
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)

    db.setup()
    migrados = 0
    omitidos = 0

    for user_id_str, perfil in data.items():
        user_id = int(user_id_str)
        with db.connect() as conn:
            conn.execute("SELECT user_id FROM jugadores WHERE user_id = ?", (user_id,))
            if conn.fetchone() is not None:
                omitidos += 1
                continue

        # Aceptar claves nuevas y viejas (job/trabajo, exp/experiencia...)
        trabajo = perfil.get("trabajo") or perfil.get("job")
        experiencia = perfil.get("experiencia", perfil.get("exp", 0)) or 0
        dinero = perfil.get("dinero", perfil.get("money", 0)) or 0
        salud = perfil.get("salud", perfil.get("health", 100))
        enfermedad = perfil.get("disease")
        fecha_trabajo = perfil.get("date_job")
        fecha_enfermedad = perfil.get("date_disease")

        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO jugadores (
                    user_id, dinero, experiencia, trabajo, fecha_trabajo,
                    salud, enfermedad, fecha_enfermedad
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    int(dinero),
                    int(experiencia),
                    trabajo,
                    fecha_trabajo,
                    int(salud),
                    enfermedad,
                    fecha_enfermedad,
                ),
            )
        migrados += 1

    print("Migrados:", migrados)
    print("Ya existían (omitidos):", omitidos)


if __name__ == "__main__":
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "legacy" / "data.json"
    migrar(ruta)
