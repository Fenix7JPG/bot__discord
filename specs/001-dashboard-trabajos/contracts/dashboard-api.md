# Contrato API: dashboard (001-dashboard-trabajos)

Base: mismo origen que el webserver (http://localhost:5000 en dev; la URL publica de
Render en produccion). HTML = paginas; JSON = endpoints para fetch del panel.

## Autenticacion (OAuth2 Discord, Authorization Code)

- `GET /panel` - pagina del panel. Sin sesion: muestra boton "Iniciar sesion con
  Discord" (enlace a la URL de autorizacion). Con sesion: lista de servidores
  administrados.
- `GET /panel/login` - genera state aleatorio (seguno en la sesion) y redirige a
  Discord (scope: identify guilds). Redirect URI = DASHBOARD_PUBLIC_URL + /panel/callback.
- `GET /panel/callback?code&state` - valida state; intercambia code por token
  (stdlib); pide /users/@me y /users/@me/guilds; guarda cuenta en dashboard_accounts;
  crea sesion web (12 h); redirige a /panel. Error de state/token: pagina de error
  con explicacion (sin sesion creada).
- `GET /panel/logout` - limpia la sesion y redirige a /panel.

## Paginas

- `GET /panel/servidor/<guild_id>` - pagina de configuracion. Requiere sesion con
  ese guild en admin_guilds y bot presente; si no: 403 con pagina de acceso denegado.
  Muestra formulario unico: Economia (work_mode, minigame, turnos, sesiones, riesgos)
  + General (welcome_channel_id, ticket_category_id, alliance_channel_id,
  hunter_role_id, alliance_role_id) + ultimos 20 registros de auditoria.
- `GET /panel/panel.css`, `GET /panel/panel.js` - estaticos del tema (mime correcto).

## Endpoints JSON

- `POST /panel/api/servidor/<guild_id>/config` - cuerpo JSON con los campos a
  cambiar (economia y/o general). Validaciones: rangos y tipos (FR-010); rechazo
  completo sin escritura parcial si algo es invalido. Requiere sesion admin del guild
  y header Origin/Host coherente (defensa CSRF, D2). Respuesta 200:
  `{ok: true, cambios: [{campo, anterior, nuevo}], auditoria: [...]}`.
  Error: `{ok: false, error: "mensaje", detalle: {campo: "regla"}}` con HTTP 400
  (validacion) o 403 (permisos/sesion) o 415 (no JSON).
- `GET /panel/api/servidor/<guild_id>/auditoria` - ultimos 20 registros.

## Codigos de error

- 401 sin sesion en endpoints JSON; 403 sin permiso del guild; 400 validacion;
  415 cuerpo no-JSON; 500 con mensaje generico (detalle solo al log).

## Permisos (D3)

- admin_guilds de la sesion = guilds del OAuth con ADMINISTRADOR (0x8) o MANAGE_GUILD
  (0x20) INTERSECT guilds donde el bot esta presente (cache en memoria del bot).
- Re-chequeado en cada endpoint (no confiar solo en la pagina).
