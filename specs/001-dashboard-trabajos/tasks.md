# Tasks: Dashboard de configuracion y trabajos estilo Nekotina

**Input**: Design documents from `/specs/001-dashboard-trabajos/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Incluidos y OBLIGATORIOS (constitution II: test-first para logica nueva).

**Organization**: Por user story (US1 turnos, US2 profesiones, US3 dashboard).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede correr en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: user story dueña de la tarea (US1, US2, US3)
- Rutas exactas en cada descripcion

## Path Conventions

Proyecto unico existente: cogs/, services/, database/, web/, tests/ en la raiz.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuracion base y assets estaticos sin logica.

- [x] T001 [P] Agregar variables de entorno nuevas (DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DASHBOARD_PUBLIC_URL, DASHBOARD_SECRET) a config.py y documentarlas en .env.example
- [x] T002 [P] Crear tema del panel en web/panel.css: oscuro propio (fondo #0f1115, tarjetas #171a21, acento #5865f2), titulos font Elephant, cuerpo Comic Sans MS, sin emojis, sin CDNs, estilos de formularios, botones, tabla de auditoria y mensajes de error

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema y repos nuevos que US1 y US3 necesitan. BLOCKS all stories.

- [x] T003 Escribir tests RED en tests/test_config_eco.py: get_economia devuelve defaults (turnos/calculo/3/2/35/30), set_economia upsert + rechazo de rangos (turnos 0 y 6, sesiones 0 y 11, riesgo -1 y 101) sin escritura parcial, auditoria registra campo/anterior/nuevo/actor/fecha ISO, campos nuevos de jugadores aceptados por actualizar_campo (dia_ultimo_trabajo, sesiones_hoy)
- [x] T004 Agregar DDL aditivo en database/database.py: tablas server_economy_config, config_audit, dashboard_accounts y ALTER TABLE idempotentes (jugadores: dia_ultimo_trabajo TEXT, sesiones_hoy INTEGER DEFAULT 0; trabajos: turnos_sugeridos INTEGER, es_riesgoso INTEGER) con try/except por 'duplicate column name'
- [x] T005 Backfill idempotente en database/catalogos.py dentro de poblar_catalogos: UPDATE de trabajos con turnos_sugeridos/es_riesgoso en NULL segun nivel (mediocre/bajo -> 2 turnos y no riesgoso; medio -> 3 y riesgoso; alto -> 4 y riesgoso)
- [x] T006 Ampliar database/jugadores_repo.py: campos dia_ultimo_trabajo y sesiones_hoy en permitidos y CAMPOS_INICIALES
- [x] T007 Implementar en database/servidor_repo.py: get_economia(guild_id) con defaults, set_economia(guild_id, valores, actor) validando rangos (turnos 1..5, sesiones 1..10, riesgos 0..100, enums work_mode/minigame) con upsert + INSERT en config_audit por campo cambiado, get_auditoria(guild_id, limit=20); dejar que tests/test_config_eco.py quede verde

**Checkpoint**: `pytest tests/test_config_eco.py -q` verde; db.setup() corre dos veces sin error (idempotencia).

---

## Phase 3: User Story 1 - Turnos de trabajo estilo Nekotina (Priority: P1) - MVP

**Goal**: /work abre una sesion de minijuego por turnos con botones, pagos por acierto, limite diario UTC y riesgo; modo cooldown clasico sigue disponible por config.

**Independent Test**: Con fakes (sin red): registrar jugador, postularlo, invocar /work, responder la vista de botones y verificar dinero/XP/limite/riesgo.

### Tests for User Story 1 (escribir PRIMERO, verificar que FALLAN)

- [x] T008 [P] [US1] Tests RED en tests/test_minijuegos.py: generar_calculo con rng fijo produce 4 opciones y 1 correcta; generar_memoria devuelve secuencia de 5 y pregunta por posicion; generar_pregunta despacha por tipo; determinismo con mismo rng
- [x] T009 [P] [US1] Tests RED en tests/test_turnos.py: crear_sesion arma sesion con pregunta 1; responder_turno acierto paga parte del sueldo y suma XP; fallo paga 0; racha perfecta suma bonus 25%; aplicar_enfermedad respeta health_loss_chance y 10 de salud con rng controlado; sesiones_disponibles resetea al cambiar dia UTC; GestorSesiones expira a los 3 min y permite una sola sesion por usuario

### Implementation for User Story 1

- [x] T010 [US1] Implementar services/minijuegos.py: generar_calculo(rng), generar_memoria(rng), generar_pregunta(tipo, rng) segun contracts/comandos.md (sin emojis en textos)
- [x] T011 [US1] Implementar services/turnos_trabajo.py: crear_sesion, responder_turno, calcular_pago_turno, calcular_bonus, calcular_xp, sesiones_disponibles, aplicar_enfermedad y GestorSesiones (expiracion 3 min, una sesion por usuario) segun contracts/comandos.md; dejar tests/test_minijuegos.py y tests/test_turnos.py en verde
- [x] T012 [US1] Crear cogs/economia/vistas_trabajo.py: VistaTurno (4 botones discord.ui, etiquetas sin emojis, disabled al responder, solo el autor de la sesion puede presionar, delega en services/turnos_trabajo)
- [x] T013 [US1] Reworkear cogs/economia/work.py: leer config del servidor (servidor_repo.get_economia); modo 'cooldown' conserva el flujo actual de 24h intacto; modo 'turnos' (default) usa GestorSesiones, guarda contador diario (dia UTC + sesiones_hoy) AL INICIAR, paga al final del turno con botones y resumen final con bonus, salud y sesiones restantes; aviso de limite con reinicio 00:00 UTC
- [x] T014 [US1] Adaptar tests/test_work.py: casos de cooldown viejos fuerzan work_mode='cooldown' en la config del servidor de prueba; agregar casos de modo turnos con interacciones falsas (primer turno enviado, respuesta por boton fake, limite diario, sin profesion, sin perfil); verificar respuesta efimera a un tercero que presiona

**Checkpoint**: `pytest tests/test_minijuegos.py tests/test_turnos.py tests/test_work.py -q` verde; US1 demostrable sola.

---

## Phase 4: User Story 2 - Lista de profesiones, postularse y renunciar (Priority: P1)

**Goal**: Lista con datos Nekotina (salario por sesion, turnos, riesgo, XP requerida), postulacion con suerte configurable y /renunciar-trabajo con confirmacion.

**Independent Test**: Con catalogo sembrado y fakes: listar, postularse con y sin XP, renunciar.

### Tests for User Story 2 (escribir PRIMERO, verificar que FALLAN)

- [x] T015 [P] [US2] Ampliar tests/test_trabajos.py: la lista muestra salario por sesion, turnos sugeridos, riesgo y XP requerida por profesion (casos por nivel: mediocre 2 turnos no riesgoso, medio 3 riesgoso, alto 4 riesgoso); paginacion existente intacta
- [x] T016 [P] [US2] Tests RED en tests/test_renunciar.py: renunciar sin profesion avisa; con profesion pide confirmacion; confirmar deja trabajo=None e informa; cancelar no cambia nada; un tercero presionando recibe efimero

### Implementation for User Story 2

- [x] T017 [US2] Ampliar cogs/economia/trabajos.py: incluir turnos_sugeridos y es_riesgoso en la lista (desde utils/datos.py si hace falta ampliar su API), textos sin emojis nuevos (los emojis del catalogo se mantienen)
- [x] T018 [US2] Modificar cogs/economia/postularse_trabajo.py: la probabilidad de entrar sin requisitos sale de servidor_repo.get_economia(guild_id)['lucky_chance'] (default 30 = comportamiento actual); mensaje menciona la configuracion del servidor
- [x] T019 [US2] Crear cogs/economia/renunciar_trabajo.py con VistaConfirmarRenuncia en cogs/economia/vistas_trabajo.py (Confirmar/Cancelar); dejar tests/test_renunciar.py en verde

**Checkpoint**: `pytest tests/test_trabajos.py tests/test_renunciar.py tests/test_postularse.py -q` verde; US1+US2 combinables (postularse -> trabajar con turnos).

---

## Phase 5: User Story 3 - Dashboard web de configuracion (Priority: P2)

**Goal**: /panel con login OAuth2 de Discord, lista de servidores admin+bot, edicion de economia y ajustes generales con validacion y auditoria, frontend HTML/CSS/JS puro.

**Independent Test**: Con test_client de Flask y OAuth simulado: login, lista de servidores, guardar config valida/invalida, permisos y auditoria.

### Tests for User Story 3 (escribir PRIMERO, verificar que FALLAN)

- [x] T020 [P] [US3] Tests RED en tests/test_dashboard_auth.py: construir_url_autorizacion arma URL con client_id, redirect_uri, scope identify guilds y state; intercambiar_codigo acepta un POST mock (monkeypatch de urllib.request.urlopen) y pide /users/@me y /users/@me/guilds; extraer_admin_guilds filtra por permisos 0x8/0x20; state invalido rechaza sin sesion; cuenta se guarda en dashboard_accounts con ultimo_login ISO
- [x] T021 [P] [US3] Tests RED en tests/test_dashboard_api.py con test_client: /panel sin sesion muestra login; callback con state valido crea sesion y lista solo guilds admin+bot; /panel/servidor/<id> 403 para no-admin y 200 para admin; POST config valida responde {ok, cambios} y persiste; POST invalido responde 400 con detalle y NO escribe; POST sin JSON 415; POST sin sesion 401; auditoria endpoint devuelve registros; Origin/Host incoherente rechazado

### Implementation for User Story 3

- [x] T022 [US3] Implementar services/dashboard/auth.py: construir_url_autorizacion, intercambiar_codigo (stdlib), obtener_usuario_y_guilds, extraer_admin_guilds, guardar_cuenta (repo inline sobre dashboard_accounts), crear_sesion/obtener_sesion (flask.session firmado con DASHBOARD_SECRET, caducidad 12 h), logout; dejar tests/test_dashboard_auth.py en verde
- [x] T023 [US3] Implementar services/dashboard/configurador.py: obtener_vista_config(guild_id) (economia + guild_config), guardar_config(guild_id, actor, cuerpo) que valide TODO antes de escribir (economia via servidor_repo.set_economia; general via servidor_repo.set_config para welcome_channel_id, ticket_category_id, alliance_channel_id, hunter_role_id, alliance_role_id), devuelve cambios y auditoria; rechazo completo sin escritura parcial
- [x] T024 [US3] Implementar blueprint services/dashboard/__init__.py con rutas /panel, /panel/login, /panel/callback, /panel/logout, /panel/servidor/<int:guild_id>, /panel/api/servidor/<int:guild_id>/config, /panel/api/servidor/<int:guild_id>/auditoria, /panel/panel.css, /panel/panel.js (HTML con render_template_string; pagina de acceso denegado y de error OAuth); registrar el blueprint desde webserver.py + registrar_bot(bot) para el cache de guilds presentes; / y /terminal sin cambios
- [x] T025 [US3] Crear web/panel.js: JS vanilla (fetch POST JSON con header JSON, repintado de resultados, mensajes de error por campo, confirmacion de guardado, sin frameworks ni CDNs); dejar tests/test_dashboard_api.py en verde

**Checkpoint**: `pytest tests/test_dashboard_auth.py tests/test_dashboard_api.py -q` verde; panel navegable con test_client.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integracion final, documentacion y validacion completa.

- [x] T026 Verificar carga real de extensiones con scripts/verificar_cogs.py (debe cargar renunciar_trabajo y el resto sin errores) y ajustar el script si lista cogs hardcoded
- [x] T027 [P] Actualizar docs/DESPLIEGE_RENDER.md y README.md: variables nuevas (DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DASHBOARD_PUBLIC_URL, DASHBOARD_SECRET), redirect URI en el portal de Discord y resumen del nuevo flujo de trabajos
- [x] T028 Correr validacion completa de quickstart.md: suite completa verde (82 previos + nuevos), verificar_cogs OK, y prueba manual opcional del panel con scripts/probar_dashboard.py (nuevo script que levanta la app Flask con la config del .env)
- [x] T029 Actualizar la skill bot-discord con el nuevo flujo (turnos, config economia, dashboard) para futuras sesiones
- [x] T030 Commit de la feature completa en main con mensaje descriptivo

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): sin dependencias, inmediato (T001, T002 paralelos)
- Foundational (Phase 2): depende de Setup; BLOCKS US1, US2 y US3 (T003 RED -> T004..T007)
- US1 (Phase 3): depende de Foundational; MVP de la feature
- US2 (Phase 4): depende de Foundational; puede hacerse en paralelo con US3, secuencial tras US1 (comparte vistas_trabajo.py con T012)
- US3 (Phase 5): depende de Foundational; independiente de US1/US2 salvo lectura de get_economia (ya en Foundational)
- Polish (Phase 6): depende de todas las stories

### User Story Dependencies

- US1 usa: get_economia (T007), campos de jugadores (T006), backfill de trabajos (T005)
- US2 usa: get_economia (T007), backfill de trabajos (T005), vistas (T012 para el patron de vistas)
- US3 usa: get_economia/set_economia/auditoria (T007), guild_config existente, config.py (T001), panel.css (T002)

### Parallel Opportunities

- T001 + T002 (Setup) en paralelo
- T008 + T009 (tests US1) y T015 + T016 (tests US2) y T020 + T021 (tests US3) en paralelo dentro de su fase
- T022 (auth) y T023 (configurador) son archivos independientes: paralelizables tras sus tests
- US2 y US3 pueden correr en paralelo si hay dos ejecutores (no comparten archivos)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2 completas (fundacion)
2. Phase 3 (US1) completa con checkpoint verde
3. STOP y validar: jugar una sesion completa con fakes; luego demo en Discord con sync por guild

### Incremental Delivery

1. Setup + Foundational -> fundacion verificada
2. US1 -> MVP interactivo de trabajos
3. US2 -> ciclo completo de profesiones
4. US3 -> dashboard configurable con auditoria
5. Polish -> docs, quickstart, commit

### Notes

- Los tests de cada story se escriben y FALLAN antes que su implementacion (constitution II)
- El codigo nuevo NO usa f-strings ni %-format; mensajes sin em-dash ni flechas
- El catalogo mantiene sus emojis existentes; la UI web y los textos nuevos de botones no usan emojis
- Commit por checkpoint de story; tareas marcadas [x] en este archivo a medida que se completan
