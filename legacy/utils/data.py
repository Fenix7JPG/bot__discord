import asyncio
import os
import json
import tempfile
PATH_USERS = "data.json"
PATH_TRABAJOS = "trabajos.json"


file_lock = asyncio.Lock()

async def load_data(path: str) -> dict:
    """
    Carga y retorna el contenido JSON del archivo `path`.
    Si el archivo no existe, crea uno con la estructura por defecto {"xp": {}, "jobs": {}}.
    Esta función es asíncrona y usa file_lock para evitar condiciones de carrera.
    """
    async with file_lock:
        # Si no existe, inicializamos con estructura base
        if not os.path.exists(path):
            default = {"xp": {}, "jobs": {}}
            await save_data(default, path)
            return default

        def _read_sync():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        data = await asyncio.to_thread(_read_sync)

        return data

async def save_data(data, path: str) -> None:
    """
    Guarda `data` como JSON en `path` de forma atómica.
    Usa un archivo temporal dentro del mismo directorio y luego lo reemplaza.
    Esta función es asíncrona y usa file_lock para evitar escrituras concurrentes.
    """
    async with file_lock:
        dirn = os.path.dirname(path) or "."
        os.makedirs(dirn, exist_ok=True)

        def _write_sync():
            # mkstemp crea un file descriptor seguro en el directorio especificado
            fd, tmp_path = tempfile.mkstemp(dir=dirn, prefix=".tmp-", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                # reemplazo atómico
                os.replace(tmp_path, path)
            finally:
                # cleanup si algo falló y tmp_path aún existe
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        await asyncio.to_thread(_write_sync)

    