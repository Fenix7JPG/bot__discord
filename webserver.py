"""Mini servidor Flask que mantiene despierto el servicio web de Render.

Render asigna un puerto externo; si no hay proceso escuchando, considera el
servicio caído. Este hilo atiende ese ping mientras el bot corre.
"""

import os
import threading

from flask import Flask

app = Flask(__name__)


@app.route("/")
def index():
    return "El bot está vivo."


def _run():
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    hilo = threading.Thread(target=_run, daemon=True)
    hilo.start()
