# Implementation Plan: Dashboard de configuracion y trabajos estilo Nekotina

**Branch**: `001-dashboard-trabajos` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-dashboard-trabajos/spec.md`

## Summary

Sistema de trabajos estilo Nekotina: sesiones de minijuego por turnos respondidas con
botones nativos de Discord, limitadas por dia UTC, con lista de profesiones (salario
por turno, riesgo, requisitos), postulacion y renuncia. El modo de trabajo (turnos o
cooldown clasico de 24h) es configurable por servidor. Dashboard web embebido en el
Flask existente con login OAuth2 de Discord, edicion de configuracion de economia y de
los ajustes ya existentes (bienvenida, tickets, alianzas), con auditoria de cambios.
Logica en servicios y repos con tests sin Discord; frontend en HTML/CSS/JS puro.

## Technical Context

**Language/Version**: Python 3.14 (interprete verificado
C:/Users/USER/AppData/Local/Python/pythoncore-3.14-64/python.exe)

**Primary Dependencies**: discord.py[voice] 2.6.3, Flask 3.1.1 (ya presente), pytest +
pytest-asyncio. OAuth2 y HTTP de Discord con stdlib (urllib.request); sesiones de
dashboard con flask.session firmado (itsdangerous, incluido en Flask). Cero
dependencias nuevas.

**Storage**: SQLite local / Turso por HTTP (fachada db existente). Cambios de esquema
aditivos: ALTER TABLE ADD COLUMN y tablas nuevas (no se tocan columnas existentes).

**Testing**: pytest (asyncio_mode=auto), interacciones falsas (tests/fakes.py), base
temporal (fixture db_local). Dashboard probado con app.test_client() de Flask.

**Target Platform**: Desarrollo en Windows; produccion Render Background Worker
(Linux) con webserver.py respondiendo en $PORT.

**Project Type**: Bot de Discord con dashboard web embebido (monolito unico).

**Performance Goals**: Interacciones de Discord respondidas en < 2 s; paginas y
endpoints del dashboard < 500 ms; una sola llamada de config por uso de comando.

**Constraints**: Plan gratuito de Render (memoria limitada, worker dormido); sin
servicios nuevos ni procesos extra; sesiones de minijuego en memoria (se pierden si el
worker se reinicia, aceptado en la spec); sync de slash por guild para pruebas.

**Scale/Scope**: Un bot con cientos de servidores como maximo; 1-3 admins por servidor
usando el dashboard; catalogo de ~101 profesiones existente.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Logica en servicios, interfaz en cogs: PASS - turnos/minijuegos/validaciones viven
  en services/ y database/; los cogs solo envian vistas y formatean mensajes.
- II. Test-first: PASS - cada story nace con tests RED (fakes + BD temporal); la suite
  previa (82 tests) debe seguir verde.
- III. Un solo camino de datos: PASS - todo por repos sobre db; esquema aditivo
  (ADD COLUMN + tablas nuevas); se amplian jugadores_repo y servidor_repo.
- IV. Codigo legible en espanol: PASS - sin f-strings ni %-format en codigo nuevo
  (concatenar), mensajes sin em-dash ni flechas, docstrings breves.
- V. Lo obsoleto no se borra: PASS - el flujo cooldown de 24h se conserva como modo
  alternativo (FR-012); nada se mueve a legacy porque sigue en uso.

Post-design: sin violaciones. Nota: servidor_repo.set_config actual usa .format() con
campo validado en lista blanca; se deja como esta (codigo funcionando) y el codigo
NUEVO usa concatenacion.

## Project Structure

### Documentation (this feature)

```text
specs/001-dashboard-trabajos/
├── plan.md              # This file
├── research.md          # Decisiones D1..D9
├── data-model.md        # Entidades y esquema
├── quickstart.md        # Guia de validacion
├── contracts/
│   ├── comandos.md      # Slash commands y botones
│   └── dashboard-api.md # Rutas web y JSON
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
bot.py                    # sin cambios de flujo (webserver ya arranca)
webserver.py              # registra el blueprint del dashboard
config.py                 # + DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DASHBOARD_SECRET
cogs/economia/
├── work.py               # flujo nuevo: modo turnos (servicio) o cooldown clasico
├── trabajos.py           # lista de profesiones ampliada (turnos, riesgo, requisitos)
├── postularse_trabajo.py # usa configuracion (prob de suerte por servidor)
└── renunciar_trabajo.py  # nuevo: dejar la profesion actual
cogs/economia/vistas_trabajo.py  # vistas de botones del minijuego (solo interfaz)
services/
├── turnos_trabajo.py     # logica: sesiones, pagos, limites diarios, riesgo
├── minijuegos.py         # generadores de preguntas: calculo y memoria
└── dashboard/
    ├── __init__.py
    ├── auth.py           # OAuth2, cuentas, sesiones, permisos de admin
    └── configurador.py   # lectura/validacion/guardado de config + auditoria
database/
├── database.py           # DDL aditivo (2 tablas nuevas + 2 ALTER)
├── jugadores_repo.py     # + campos dia_ultimo_trabajo, sesiones_hoy
└── servidor_repo.py      # + config economia (upsert) y auditoria
web/
├── panel.css             # tema oscuro propio, sin emojis
└── panel.js              # vanilla JS: guardar formularios via fetch
tests/
├── test_turnos.py        # pagos, limites, riesgo (RED primero)
├── test_minijuegos.py    # generadores deterministas
├── test_config_eco.py    # upsert, rangos, auditoria
├── test_dashboard_auth.py# OAuth mock, permisos, sesiones
├── test_dashboard_api.py # endpoints con test_client
└── test_work.py          # adaptado al nuevo flujo (2 modos)
```

**Structure Decision**: Monolito existente ampliado: servicios para logica nueva,
blueprint de dashboard dentro del Flask de keep-alive, frontend estatico en web/.
No hay proyectos ni procesos nuevos (constitution V y constraint de Render).
