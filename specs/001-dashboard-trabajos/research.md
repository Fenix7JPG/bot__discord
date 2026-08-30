# Research: Dashboard y trabajos estilo Nekotina

**Feature**: 001-dashboard-trabajos | **Date**: 2026-08-30

## D1: Login del dashboard con Discord (OAuth2 Authorization Code)

- **Decision**: Flujo Authorization Code de Discord con stdlib (urllib.request):
  autorizar en https://discord.com/oauth2/authorize (scope identify + guilds),
  intercambiar el codigo en https://discord.com/api/oauth2/token, y consultar
  https://discord.com/api/users/@me y /users/@me/guilds. Credenciales por entorno:
  DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DASHBOARD_PUBLIC_URL (para armar la
  redirect_uri absoluta). Sin dependencias nuevas.
- **Rationale**: El usuario pidio "logear con Discord, sin login propio"; stdlib sigue
  el patron ya validado del adaptador Turso (HTTP puro). La lista de guilds del OAuth
  trae el bitfield de permisos por servidor: sirve para saber donde es admin sin
  llamadas extra.
- **Alternatives**: libreria requests/oauthlib (dependencia nueva, rechazada);
  JDA-style bot fetch de miembros (requiere Guilds intent + presencias, mas fragil).

## D2: Sesion web y CSRF

- **Decision**: flask.session (cookie firmada con itsdangerous, incluido en Flask).
  Clave de firma: DASHBOARD_SECRET; si no existe, se usa LOG_PASSWORD; si tampoco,
  una clave aleatoria por proceso (las sesiones caducan al reiniciar: aceptable).
  Cookie con SameSite=Lax; los POST del panel son JSON y el backend rechaza peticiones
  cuyo header Origin no coincida con el Host (defensa CSRF sin tokens extra).
- **Rationale**: cero dependencias y suficiente para 1-3 admins por servidor.
- **Alternatives**: tokens CSRF por formulario (mas codigo para la misma garantia en
  este alcance); JWT propio (no aporta aqui).

## D3: Permisos de administrador en el dashboard

- **Decision**: Un usuario ve/edita solo servidores donde (a) el bot esta presente
  (ids cacheados del propio bot en memoria, actualizados en on_ready y al unirse) y
  (b) el bitfield de permisos del guild (desde OAuth) incluye ADMINISTRADOR (0x8) o
  MANAGE_GUILD (0x20). Verificacion en cada endpoint, no solo en el login.
- **Rationale**: cumple FR-008 sin unir el bot a nada nuevo ni llamar a la API REST
  por cada guild.
- **Alternatives**: chequear rol de admin via API REST por guild (N+1 llamadas,
  rate limits).

## D4: Configuracion de economia por servidor

- **Decision**: Tabla nueva server_economy_config (guild_id PK, work_mode
  TEXT 'turnos'|'cooldown', minigame TEXT 'calculo'|'memoria', turns_per_session
  INTEGER, sessions_per_day INTEGER, health_loss_chance INTEGER, lucky_chance
  INTEGER). Defaults del spec (turnos, calculo, 3, 2, 35, 30). Upsert por servidor;
  lectura fresca en cada uso de comando (FR-011).
- **Rationale**: separada de guild_config (que es de canales/roles) para no tocar
  codigo existente y validar rangos por campo.
- **Alternatives**: columnas nuevas en guild_config (mezcla conceptos y obliga a
  migrar lecturas existentes).

## D5: Auditoria de configuracion

- **Decision**: Tabla nueva config_audit (id INTEGER PRIMARY KEY, guild_id, actor_id,
  actor_name, campo, valor_anterior, valor_nuevo, fecha ISO UTC). Un INSERT por campo
  cambiado dentro del guardado; el dashboard muestra los ultimos 20 registros del
  servidor.
- **Rationale**: FR-013 con esquema trivial compatible sqlite/Turso.
- **Alternatives**: log en memoria del webserver (se pierde al reiniciar).

## D6: Motor de turnos (logica pura)

- **Decision**: services/turnos_trabajo.py con funciones puras (entradas: config,
  trabajo, perfil, rng; salidas: resultados de turno y totales) + GestorSesiones en
  memoria {user_id: SesionTurnos} con expiracion de 3 minutos y una sesion activa por
  usuario. Pagos: salario repartido en turnos iguales (+ bonus de 25% si todos los
  turnos aciertan); XP = 20% del salario repartido igual; fallo paga 0 y en trabajos
  riesgosos tira health_loss_chance para perder 10 de salud.
- **Rationale**: logica probable sin Discord (constitution II), interfaz de cog
  delgada; el manager solo guarda estado efimero (aceptado en spec Edge Cases).
- **Alternatives**: persistir la sesion (innecesario para 3 min de juego);
  pagos aleatorios por turno (no determinista para tests, rechazado).

## D7: Minijuegos con botones

- **Decision**: services/minijuegos.py genera preguntas deterministas (rng inyectado):
  calculo (a +/-/* b, 4 opciones de boton, una correcta) y memoria (secuencia de 5
  palabras en el embed, botones con 4 candidatos para "cual era la N-esima"). Los
  botones son Discord UI nativo (discord.ui.View); etiquetas de texto sin emojis.
- **Rationale**: ambos son generables al vuelo, verificables con rng fijo y cubren
  FR-005; botones = decision del usuario (mejor UX movil).
- **Alternatives**: trivia con banco de preguntas fijo (mantenimiento de contenido);
  respuestas escritas (rechazada por el usuario).

## D8: Esquema aditivo y dias UTC

- **Decision**: ALTER TABLE ADD COLUMN para jugadores (dia_ultimo_trabajo TEXT,
  sesiones_hoy INTEGER DEFAULT 0) y trabajos (turnos_sugeridos INTEGER,
  es_riesgoso INTEGER DEFAULT 0). SQLite/libsql no soportan ADD COLUMN IF NOT EXISTS:
  se ejecuta el ALTER dentro de try/except ignorando el error "duplicate column
  name" (idempotente en ambos motores). Dia UTC como texto YYYY-MM-DD comparado con
  el actual: el contador se resetea solo cuando cambia el dia. El enriquecimiento de
  trabajos existentes (turnos/riesgo derivados del nivel) va en poblar_catalogos como
  UPDATE idempotente para filas con esos campos en NULL.
- **Rationale**: sin migraciones destructivas (constitution III); sin job de
  medianoche (assumption del spec).
- **Alternatives**: tabla aparte de contadores diarios (join por uso, innecesario).

## D9: Frontend del panel

- **Decision**: web/panel.css y web/panel.js estaticos servidos por el blueprint;
  HTML renderizado con render_template_string (plantillas en el modulo, sin carpeta
  templates para no interferir con nada existente). Tema oscuro propio: fondo
  #0f1115, tarjetas #171a21, acento #5865f2 (guiño Discord sin copiar), tipografias
  font-family Elephant para titulos y Comic Sans MS para cuerpo (instaladas en
  Windows), sin emojis en la UI. JS vanilla: fetch POST JSON y repintado minimo.
- **Rationale**: decision del usuario (solo HTML/CSS/JS, nada generico).
- **Alternatives**: Bootstrap/Tailwind por CDN (rechazado); Jinja con herencia de
  plantillas (sobre-ingenieria para 3 paginas).

## D10: Integracion con el webserver existente

- **Decision**: El dashboard es un Blueprint (services/dashboard) registrado desde
  webserver.py en la app Flask ya existente; keep_alive() sigue igual y las rutas
  / y /terminal no cambian. El bot (commands.Bot) se registra en el blueprint via
  webserver.registrar_bot(bot) para que el panel pueda listar guilds presentes.
- **Rationale**: un solo proceso en Render (constraint), riesgo minimo para el visor
  de logs que ya funciona.
- **Alternatives**: segundo servicio web (violaria el constraint de Render free y
  el presupuesto del usuario).
