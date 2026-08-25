"""Migra todos los datos locales a la base de datos destino.

Fuentes que consolida:
1. legacy/data.json      perfiles del juego del bot viejo
2. legacy/data/bot.db    guild_config + alliance_ranking de la BD vieja
3. legacy/Chambas.txt    catalogo de trabajos (via database.catalogos)

Destino: la base configurada en .env (TURSO_URL + TURSO_AUTH_TOKEN -> Turso;
si no hay token, la SQLite local). Idempotente: los perfiles existentes se
omiten y las filas de servidor/ranking se actualizan con upsert.

Uso:
    python scripts/migrar_a_turso.py
"""

import json
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings  # noqa: E402
from database import catalogos  # noqa: E402
from database.database import db  # noqa: E402

RUTA_DATA_JSON = BASE_DIR / "legacy" / "data.json"
RUTA_BOT_DB_VIEJA = BASE_DIR / "legacy" / "data" / "bot.db"


def _fila_vieja_a_dict(row) -> dict:
    return {clave: row[clave] for clave in row.keys()}


def migrar_perfiles_json() -> tuple[int, int]:
    """Perfiles de legacy/data.json -> tabla jugadores."""
    if not RUTA_DATA_JSON.exists():
        print("Sin legacy/data.json, se omite")
        return 0, 0

    with open(RUTA_DATA_JSON, "r", encoding="utf-8") as f:
        perfiles = json.load(f)

    migrados = 0
    omitidos = 0
    for user_id_str, perfil in perfiles.items():
        user_id = int(user_id_str)
        with db.connect() as conn:
            conn.execute("SELECT user_id FROM jugadores WHERE user_id = ?", (user_id,))
            if conn.fetchone() is not None:
                omitidos += 1
                continue

        trabajo = perfil.get("trabajo") or perfil.get("job")
        experiencia = perfil.get("experiencia", perfil.get("exp", 0)) or 0
        dinero = perfil.get("dinero", perfil.get("money", 0)) or 0

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
                    perfil.get("date_job"),
                    int(perfil.get("salud", perfil.get("health", 100))),
                    perfil.get("disease"),
                    perfil.get("date_disease"),
                ),
            )
        migrados += 1
    return migrados, omitidos


def migrar_servidores() -> int:
    """guild_config y alliance_ranking de la BD vieja -> tablas nuevas.

    Mapeo de columnas viejas: ticket_channel_id -> ticket_category_id,
    welcome_channel_id igual, resto iguales.
    """
    if not RUTA_BOT_DB_VIEJA.exists():
        print("Sin legacy/data/bot.db, se omite")
        return 0

    vieja = sqlite3.connect(RUTA_BOT_DB_VIEJA)
    vieja.row_factory = sqlite3.Row

    configs = [_fila_vieja_a_dict(r) for r in vieja.execute("SELECT * FROM guild_config")]
    rankings = [_fila_vieja_a_dict(r) for r in vieja.execute("SELECT * FROM alliance_ranking")]

    # El esquema viejo usaba otros nombres de columna en algunas filas;
    # normalizar leyendo por nombre si existe.
    for fila in configs:
        guild_id = fila["guild_id"]
        campos = {
            "welcome_channel_id": fila.get("welcome_channel_id") or fila.get("welcome_channel"),
            "ticket_category_id": fila.get("ticket_category_id") or fila.get("ticket_channel"),
            "alliance_channel_id": fila.get("alliance_channel_id") or fila.get("alliance_channel"),
            "hunter_role_id": fila.get("hunter_role_id") or fila.get("hunter_role"),
            "alliance_role_id": fila.get("alliance_role_id") or fila.get("alliance_role"),
        }
        for campo, valor in campos.items():
            if valor is not None:
                with db.connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO guild_config (guild_id, {campo}) VALUES (?, ?)
                        ON CONFLICT(guild_id) DO UPDATE SET {campo} = excluded.{campo}
                        """.format(campo=campo),
                        (guild_id, valor),
                    )

    for fila in rankings:
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO alliance_ranking (guild_id, user_id, points)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET points = excluded.points
                """,
                (fila["guild_id"], fila["user_id"], fila["points"]),
            )

    vieja.close()
    return len(configs) + len(rankings)


def main():
    print("Destino:", settings.turso_url if db.mode == "turso" else settings.db_path)
    print("Modo:", db.mode)

    # 1. Tablas + catalogos (trabajos/enfermedades desde Chambas.txt)
    db.setup()
    with db.connect() as conn:
        conn.execute("SELECT COUNT(*) AS n FROM trabajos")
        n_trabajos = conn.fetchone()["n"]
        conn.execute("SELECT COUNT(*) AS n FROM enfermedades")
        n_enfermedades = conn.fetchone()["n"]
    print("Catalogos en la BD:", n_trabajos, "trabajos,", n_enfermedades, "enfermedades")

    # 2. Perfiles del data.json viejo
    migrados, omitidos = migrar_perfiles_json()
    print("Perfiles migrados:", migrados, "| ya existian (omitidos):", omitidos)

    # 3. Servidores y ranking de la BD local vieja
    filas_servidor = migrar_servidores()
    print("Filas de servidores/ranking migradas:", filas_servidor)

    # Resumen final
    catalogos.limpiar_cache()
    with db.connect() as conn:
        conn.execute("SELECT COUNT(*) AS n FROM jugadores")
        total_jugadores = conn.fetchone()["n"]
        conn.execute("SELECT COUNT(*) AS n FROM alliance_ranking")
        total_ranking = conn.fetchone()["n"]
        conn.execute("SELECT COUNT(*) AS n FROM guild_config")
        total_servidores = conn.fetchone()["n"]
    print("")
    print("RESUMEN en", ("Turso" if db.mode == "turso" else settings.db_path))
    print("  jugadores:", total_jugadores)
    print("  ranking alianzas:", total_ranking)
    print("  servidores config:", total_servidores)
    print("  trabajos:", n_trabajos)
    print("  enfermedades:", n_enfermedades)


if __name__ == "__main__":
    main()
