# Constitution del Bot de Discord (bot__discord)

## Core Principles

### I. Logica en servicios, interfaz en cogs
La regla de negocio (economia, turnos, permisos, configuracion) vive en modulos de
servicio y repos consultables sin Discord; los cogs solo interpretan interacciones
y formatean mensajes. Esto permite probar la logica sin red ni Discord real.

### II. Test-first para logica nueva (NON-NEGOTIABLE)
Toda regla nueva (turnos, validaciones, permisos, auditoria) nace con tests que
fallan primero; la suite debe estar verde antes de cerrar cada user story. Los
tests no usan red ni Discord real: interacciones falsas y BD temporal local.

### III. Un solo camino de datos
Toda persistencia pasa por database/*_repo.py sobre la fachada db (dual
sqlite/Turso). Nada de JSON suelto: los catalogos son tablas sembradas de forma
idempotente. Los cambios de esquema son aditivos (ALTER TABLE ADD COLUMN) para
no romper la base remota existente.

### IV. Codigo legible en espanol
Sin f-strings ni %-format: concatenar con + str() y comas en print. Mensajes al
usuario sin em-dash (usar guion normal -) y sin flechas. Docstrings breves en
espanol. Interfaz separada de la logica. Codigo claro antes que compacto.

### V. Lo obsoleto no se borra
El codigo viejo va a legacy/ (solo lectura). Los comandos existentes no rompen:
las mejoras son compatibles hacia atras y migran datos si hace falta.

## Restricciones adicionales

- Despliegue: Render Background Worker con webserver.py (Flask) como keep-alive;
  el dashboard vive en ese mismo proceso Flask, no en una app aparte.
- Slash commands: para probar rapido, sync por guild; el sync global tarda hasta
  1 hora en propagarse (no es un bug).
- Fechas siempre ISO UTC (datetime.now(tz=timezone.utc).isoformat()); parsear con
  fromisoformat y asumir UTC si viene naive.
- Secretos (token, OAuth2, sesion) solo por variables de entorno; nada hardcodeado.

## Governance

- Esta constitution manda sobre preferencias ad-hoc del dia; para enmendarla se
  actualiza este archivo con version y fecha.
- Gate de implement: checklists completos + suite completa verde antes de dar
  una fase por terminada.

**Version**: 1.0.0 | **Ratified**: 2026-08-29 | **Last Amended**: 2026-08-29
