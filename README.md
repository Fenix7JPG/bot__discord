# Bot de Discord (bot__discord)

Bot multifunción para Discord: economía con trabajos y enfermedades, juegos
(blackjack, ruleta, ruleta rusa, dados), música desde SoundCloud, radio 24/7,
sistema de alianzas entre servidores, tickets de soporte, bienvenida,
confesiones anónimas y respuestas con IA al mencionar al bot.

## Estructura del proyecto

```
bot.py                 Punto de entrada: carga cogs/, sincroniza slash commands
config.py              Configuración por variables de entorno (.env)
webserver.py           Servidor Flask keep-alive para Render
cogs/
    economia/          jugar, trabajos, postularse-trabajo, work, stats, curarse
    diversion/         blackjack, ruleta, ruleta-rusa, confesion, dados
    musica/            play (SoundCloud) y radio (streams 24/7)
    alianzas/          configuración y ranking de cazadores de alianzas
    tickets/           sistema de tickets de soporte
    bienvenida/        mensaje de bienvenida a nuevos miembros
    interaccion/       /interact pat, /interact punch (GIFs)
    admin/             sync, getpaths, checkffmpeg
    utils/             ping, eco
    ia_chat.py         respuesta con IA al mencionar al bot
    ytmp3.py           descarga de audio de YouTube como MP3
database/
    database.py        Capa dual: SQLite local o Turso remoto (misma API)
    catalogos.py       Catalogos del juego sembrados en la BD (trabajos y enfermedades)
    jugadores_repo.py  Perfiles de jugadores (dinero, trabajo, salud)
    servidor_repo.py   Configuración por servidor y ranking de alianzas
services/
    ia.py              Cliente de IA (Cohere)
    turnos_trabajo.py  Motor de turnos de trabajo (pagos, limites, riesgo)
    minijuegos.py      Generadores de preguntas: calculo y memoria
    dashboard/         Panel web (/panel): OAuth2, config y auditoria
utils/
    datos.py           Lectura y búsqueda sobre los catálogos en la BD
web/
    panel.css, panel.js   Tema y logica del panel (HTML/CSS/JS puro)
tests/                 Suite pytest automática (sin red ni Discord real)
docs/                  Documentación extra (despliegue, ideas del juego)
legacy/                Código viejo conservado como referencia. NO se usa.
scripts/               Utilidades: migrar datos locales a Turso, probar conexión
```

## Comandos principales

| Comando | Qué hace |
| --- | --- |
| /jugar | Registra tu perfil del juego |
| /trabajos | Lista paginada con sueldo por sesion, turnos, riesgo y XP requerida |
| /postularse-trabajo | Postúlate a un trabajo (según tu XP y la suerte del servidor) |
| /renunciar-trabajo | Deja tu profesion actual (con confirmacion) |
| /work | Trabaja: sesion de minijuego por turnos con botones (limite diario) o modo 24h clasico, segun config del servidor |
| /stats | Tu dinero, XP, trabajo y salud |
| /curarse | Cura salud gastando dinero |
| /blackjack, /ruleta, /ruleta-rusa, /d6, /d10, /d20 | Juegos |
| /play, /queue, /skip, /stop | Música desde SoundCloud |
| /playradio, /stations | Radio en vivo 24/7 |
| /ranking_alianzas, /alianzas_perfil | Cazadores de alianzas |
| /setwelcome, /setticket, /setalianzachannel | Configuración (admins) |
| /confesion | Confesión anónima |
| /ytmp3 | Descarga audio de YouTube como MP3 |

## Dashboard web (/panel)

El mismo servidor Flask del bot sirve un panel de configuracion en `/panel`:

- Login con Discord (OAuth2): solo ves servidores donde eres administrador y
  el bot esta presente. Variables: DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET,
  DASHBOARD_PUBLIC_URL y DASHBOARD_SECRET (ver .env.example).
- Economia y trabajos por servidor: modo de trabajo (turnos estilo Nekotina o
  cooldown clasico de 24h), minijuego (calculo o memoria), turnos por sesion,
  sesiones por dia, riesgo de salud por fallo y probabilidad de entrada sin
  requisitos.
- Ajustes generales: canal de bienvenida, categoria de tickets y canal de
  alianzas (los mismos que los comandos /set...).
- Auditoria: cada guardado registra autor, valores anteriores y nuevos.

## Requisitos

- Python 3.11+ 
- FFmpeg instalado y en el PATH (música, radio y /ytmp3)

## Instalación local

```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     (Windows)
cp .env.example .env                              y rellenar DISCORD_TOKEN
python bot.py
```

Base de datos: si no defines TURSO_AUTH_TOKEN, el bot crea y usa una base
SQLite local en datos/bot.db automáticamente. Para usar Turso define:

```
DB_MODE=turso
TURSO_URL=libsql://botdiscordzeku-fenix7jpg.aws-us-east-1.turso.io
TURSO_AUTH_TOKEN=<token de Turso>
```

## Datos

Todo vive en la base de datos (local o Turso, según el modo):

| Tabla | Contenido |
| --- | --- |
| jugadores | Perfiles: dinero, XP, trabajo, salud, enfermedad, sesiones del dia |
| trabajos | Catálogo de 101 puestos en 4 niveles (turnos sugeridos y riesgo incluidos) |
| enfermedades | Catálogo de 10 enfermedades del juego |
| guild_config | Configuración por servidor (canales y roles) |
| server_economy_config | Economia por servidor: modo, minijuego, turnos, riesgos |
| config_audit | Auditoria de cambios de configuracion (autor y valores) |
| dashboard_accounts | Cuentas de Discord vinculadas al panel |
| alliance_ranking | Ranking de cazadores de alianzas |

Los catálogos se siembran automáticamente la primera vez que arranca el bot
(`db.setup()`), a partir de `database/catalogos.py` (que genera los trabajos
desde legacy/Chambas.txt con las reglas de sueldo de info.txt).

Migra los datos de instalaciones viejas (data.json + bot.db local) a Turso:

```
python scripts/migrar_a_turso.py
```

## Despliegue en Render

Ver docs/DESPLIEGE_RENDER.md. Resumen: Worker (o Background Worker) con
build command `bash render-build.sh` y start command `python bot.py`;
variables DISCORD_TOKEN, DB_MODE=turso, TURSO_URL, TURSO_AUTH_TOKEN;
cookies de YouTube opcionales como Secret File.

## Tests

La suite prueba cada comando invocándolo con interacciones falsas: no hay red
ni conexión real a Discord.

```
python -m pytest tests/ -q
```
