"""Capa de acceso a datos con soporte dual: SQLite local y Turso.

Todo el bot usa `db` (instancia única de Database) y nunca conoce el motor
real por debajo:

- Modo "local": sqlite3 estándar contra un archivo en datos/.
- Modo "turso": protocolo Hrana sobre HTTP (endpoint /v2/pipeline), igual que
  en el proyecto gestor_de_tareas. Solo stdlib, sin dependencias extra.

El esquema vive aquí como lista de sentencias DDL y se ejecuta una a una,
lo que funciona idéntico en SQLite y en Turso.
"""

import base64
import json
import sqlite3
import urllib.request
from typing import Any, Sequence

from config import settings

# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS guild_config (
        guild_id INTEGER PRIMARY KEY,
        welcome_channel_id INTEGER,
        ticket_category_id INTEGER,
        alliance_channel_id INTEGER,
        hunter_role_id INTEGER,
        alliance_role_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alliance_ranking (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """,
    # Un perfil por usuario GLOBAL (no por servidor): el juego es progresión personal
    """
    CREATE TABLE IF NOT EXISTS jugadores (
        user_id INTEGER PRIMARY KEY,
        dinero INTEGER NOT NULL DEFAULT 0,
        experiencia INTEGER NOT NULL DEFAULT 0,
        trabajo TEXT,
        fecha_trabajo TEXT,
        salud INTEGER NOT NULL DEFAULT 100,
        enfermedad TEXT,
        fecha_enfermedad TEXT
    )
    """,
    # Catalogos de contenido del juego (sembrados por database.catalogos)
    """
    CREATE TABLE IF NOT EXISTS trabajos (
        slug TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        emoji TEXT NOT NULL DEFAULT '',
        level TEXT NOT NULL,
        required_experience INTEGER NOT NULL DEFAULT 0,
        sueldo INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS enfermedades (
        slug TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        severity TEXT NOT NULL,
        health_loss INTEGER NOT NULL,
        duration_days INTEGER NOT NULL,
        treatment_cost INTEGER NOT NULL DEFAULT 0,
        description TEXT NOT NULL DEFAULT ''
    )
    """,
]

DDL_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_alliance_points ON alliance_ranking(guild_id, points DESC)",
]


# ---------------------------------------------------------------------------
# Utilidades de conversión Hrana (protocolo de Turso)
# ---------------------------------------------------------------------------

def _escape_literal(value: Any) -> str:
    """Convierte un valor Python en literal SQL seguro (solo para batch)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _hrana_value(v: Any) -> dict:
    """Valor Python al formato de argumento Hrana."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "real", "value": str(v)}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"type": "blob", "value": base64.b64encode(bytes(v)).decode("ascii")}
    return {"type": "text", "value": str(v)}


def _from_hrana(v: dict) -> Any:
    """Valor Hrana de la respuesta a Python."""
    tipo = v.get("type")
    if tipo == "null":
        return None
    if tipo == "integer":
        return int(v["value"])
    if tipo == "text":
        return v["value"]
    if tipo == "real":
        return float(v["value"])
    if tipo == "blob":
        return base64.b64decode(v["value"])
    return v.get("value")


def _render_sql(sql: str, params: Sequence[Any]) -> str:
    """Interpola parámetros posicionales (?) como literales seguros.

    Se usa solo en modo transacción remota, donde Turso no acepta args
    separados dentro de un batch.
    """
    it = iter(params)
    partes = []
    for char in sql:
        if char == "?":
            try:
                partes.append(_escape_literal(next(it)))
            except StopIteration:
                partes.append("?")
        else:
            partes.append(char)
    return "".join(partes)


class TursoError(Exception):
    """Error devuelto por el servidor Turso."""


class TursoConnection:
    """Cliente Turso por HTTP con API parecida a sqlite3.

    Expone execute/fetchall/fetchone/commit/rollback para que el resto del
    código trate ambas conexiones igual. Las filas son dicts.
    """

    def __init__(self, url: str, auth_token: str):
        self._base_url = url.replace("libsql://", "https://").rstrip("/")
        self._token = auth_token
        self._cols: list[str] = []
        self._rows: list[list[dict]] = []
        self._in_tx = False
        self._buffer: list[str] = []

    # -- transporte ---------------------------------------------------------
    def _pipeline(self, requests: list[dict]) -> list[dict]:
        body = json.dumps({"requests": requests}).encode("utf-8")
        req = urllib.request.Request(
            self._base_url + "/v2/pipeline",
            data=body,
            headers={
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        for r in payload.get("results", []):
            if r.get("type") == "error":
                raise TursoError(r["error"]["message"])
        return payload["results"]

    def _ok(self, resultado: dict) -> dict:
        if resultado.get("type") != "ok":
            msg = resultado.get("error", {}).get("message", "error desconocido")
            raise TursoError(msg)
        return resultado["response"]["result"]

    # -- API estilo sqlite3 ---------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] = ()) -> "TursoConnection":
        if self._in_tx:
            # Transacción remota: acumular y enviar todo junto en el commit
            self._buffer.append(_render_sql(sql, params))
            self._cols, self._rows = [], []
            return self

        stmt = {"sql": sql, "args": [_hrana_value(p) for p in (params or ())]}
        result = self._ok(self._pipeline([{"type": "execute", "stmt": stmt}])[0])
        self._cols = [c.get("name") for c in result.get("cols") or []]
        self._rows = result.get("rows") or []
        return self

    def fetchall(self) -> list[dict]:
        return [
            {nombre: _from_hrana(row[i]) for i, nombre in enumerate(self._cols)}
            for row in self._rows
        ]

    def fetchone(self) -> dict | None:
        rows = self.fetchall()
        return rows[0] if rows else None

    # Turso cierra cada petición HTTP; commit/rollback solo vacían el buffer
    def commit(self):
        if not self._in_tx:
            return
        self._in_tx = False
        if self._buffer:
            stmts = [{"sql": s} for s in self._buffer]
            self._pipeline([{"type": "batch", "batch": {"steps": [{"type": "execute", "stmt": s} for s in stmts]}}])
            self._buffer = []

    def rollback(self):
        self._in_tx = False
        self._buffer = []

    def close(self):
        pass

    # Soporte de "with connect() as conn:" igual que sqlite3
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


class LocalConnection(TursoConnection):
    """No usado: sqlite3 ya cumple la misma interfaz. Existe por claridad."""

    pass


class Database:
    """Fachada única del bot: decide motor según settings.db_mode."""

    def __init__(self):
        mode = settings.db_mode
        if not mode:
            # Autodetección: turso si hay token, si no archivo local
            mode = "turso" if settings.turso_auth_token else "local"
        self.mode = mode

    def connect(self):
        if self.mode == "turso":
            return TursoConnection(settings.turso_url, settings.turso_auth_token)
        # En local, garantizar que exista el directorio del archivo
        import os

        carpeta = os.path.dirname(settings.db_path)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        conn = sqlite3.connect(settings.db_path)
        conn.row_factory = sqlite3.Row
        return _SQLiteCompat(conn)

    def setup(self):
        """Crea las tablas si no existen y siembra catalogos vacios."""
        with self.connect() as conn:
            for ddl in DDL_STATEMENTS:
                conn.execute(ddl)
            for idx in DDL_INDICES:
                conn.execute(idx)

        # Los catalogos (trabajos/enfermedades) se siembran solo la primera
        # vez; si ya tienen filas no se tocan para respetar ediciones manuales.
        from database.catalogos import poblar_catalogos

        with self.connect() as conn:
            conn.execute("SELECT COUNT(*) AS n FROM trabajos")
            hay_trabajos = conn.fetchone()["n"] > 0
            conn.execute("SELECT COUNT(*) AS n FROM enfermedades")
            hay_enfermedades = conn.fetchone()["n"] > 0

        if not hay_trabajos or not hay_enfermedades:
            poblar_catalogos()


class _SQLiteCompat:
    """Envuelve sqlite3.Connection y expone fetchone() que devuelve dict.

    sqlite3 con row_factory=sqlite3.Row devuelve filas que ya soportan
    fila["columna"]; aquí solo convertimos fetchone() a dict|None para que
    ambos motores se comporten igual.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> "_SQLiteCompat":
        # sqlite3 devuelve un cursor por execute; lo guardamos para fetch*
        self._cursor = self._conn.execute(sql, tuple(params))
        return self

    def fetchall(self) -> list[dict]:
        return [dict(row) for row in self._cursor.fetchall()]

    def fetchone(self) -> dict | None:
        row = self._cursor.fetchone()
        return dict(row) if row else None

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


db = Database()
