# Data Model: Dashboard y trabajos estilo Nekotina

**Feature**: 001-dashboard-trabajos | **Date**: 2026-08-30

## Entidades

### trabajos (catalogo, tabla existente ampliada)

| Campo | Tipo | Reglas |
|-------|------|--------|
| slug | TEXT PK | ya existe |
| name, emoji, level, required_experience, sueldo | ya existen | sin cambios |
| turnos_sugeridos | INTEGER NULL | NUEVO: 2 (mediocre/bajo), 3 (medio), 4 (alto); backfill idempotente |
| es_riesgoso | INTEGER 0/1 NULL | NUEVO: 0 en mediocre/bajo, 1 en medio/alto; backfill idempotente |

"sueldo" pasa a interpretarse como salario total por SESION (repartido entre los
turnos). En modo cooldown sigue siendo el pago base del flujo clasico.

### jugadores (perfil, tabla existente ampliada)

| Campo | Tipo | Reglas |
|-------|------|--------|
| user_id, dinero, experiencia, trabajo, fecha_trabajo, salud, enfermedad, fecha_enfermedad | ya existen | sin cambios |
| dia_ultimo_trabajo | TEXT NULL | NUEVO: 'YYYY-MM-DD' UTC del dia con actividad |
| sesiones_hoy | INTEGER DEFAULT 0 | NUEVO: sesiones de trabajo hechas en dia_ultimo_trabajo; se resetea al cambiar el dia |

### server_economy_config (NUEVA, una fila por servidor)

| Campo | Tipo | Reglas |
|-------|------|--------|
| guild_id | INTEGER PK | |
| work_mode | TEXT | 'turnos' (default) o 'cooldown' |
| minigame | TEXT | 'calculo' (default) o 'memoria' |
| turns_per_session | INTEGER | 1..5, default 3 |
| sessions_per_day | INTEGER | 1..10, default 2 |
| health_loss_chance | INTEGER | 0..100 (%), default 35 |
| lucky_chance | INTEGER | 0..100 (%), default 30 (entrada sin requisitos) |

### guild_config (existente, editada desde el dashboard)

welcome_channel_id, ticket_category_id, alliance_channel_id, hunter_role_id,
alliance_role_id (INTEGER NULL). El dashboard edita los tres primeros + los roles.

### config_audit (NUEVA)

| Campo | Tipo | Reglas |
|-------|------|--------|
| id | INTEGER PK (rowid) | |
| guild_id | INTEGER NOT NULL | |
| actor_id / actor_name | INTEGER / TEXT | quien guardo |
| campo | TEXT | nombre del campo cambiado |
| valor_anterior / valor_nuevo | TEXT | NULL se guarda como '' |
| fecha | TEXT | datetime.now(tz=utc).isoformat() |

### dashboard_accounts (NUEVA, cuentas vinculadas OAuth)

| Campo | Tipo | Reglas |
|-------|------|--------|
| discord_id | INTEGER PK | id del usuario de Discord |
| username | TEXT | nombre visible al momento del login |
| ultimo_login | TEXT | ISO UTC |

Los servidores donde administra NO se persisten (cambian a cada rato): se derivan del
OAuth de la sesion vigente. La tabla deja rastro estable de cuentas que usaron el panel.

### SesionTurnos (efimera, en memoria)

user_id, guild_id, canal_id, mensaje_id, trabajo(slug), turnos_totales, turno_actual,
aciertos, pagado, xp_ganada, pregunta_actual(dict), expira(datetime UTC +3 min).
No persiste: si el worker se reinicia, la sesion se pierde y los turnos cobrados del
dia quedan respetados (Edge Case del spec).

### Sesion web (cookie firmada flask.session)

discord_id, username, admin_guilds (lista de ids donde admin), creada (epoch).
Caduca a las 12 horas. Contenido minimo, firmado con DASHBOARD_SECRET.

## Transiciones de estado relevantes

- Sesiones de trabajo por dia: si jugador.dia_ultimo_trabajo != hoy(UTC) ->
  sesiones_hoy se considera 0 y ambos campos se sobrescriben al trabajar.
- Limite alcanzado: sesiones_hoy >= sessions_per_day -> mensaje con hora de reinicio
  (00:00 UTC) y sin pago.
- Configuracion: lectura siempre fresca por uso; guardado = upsert + INSERT auditoria.
- Sesion de minijuego: activa -> respondida turno a turno -> finalizada (resumen) o
  expirada (mensaje "sesion expirada").

## Validaciones (dashboard)

- work_mode in {'turnos','cooldown'}; minigame in {'calculo','memoria'}.
- turns_per_session 1..5; sessions_per_day 1..10; health_loss_chance 0..100;
  lucky_chance 0..100.
- IDs de canal/categoria/roles: enteros positivos o vacio (limpia el ajuste).
- Fuera de rango: rechazo con mensaje del rango valido (FR-010); sin escritura parcial
  (se validan todos los campos antes del upsert).
