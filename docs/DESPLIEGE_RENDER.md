# Despliegue en Render

El bot se hostea en Render como un Background Worker que corre `python bot.py`.
El webserver.py interno (Flask) existe para que el servicio responda al health
check en el puerto que Render asigna (variable PORT).

## Pasos

1. Crea un nuevo servicio en Render apuntando al repo de GitHub.
2. Tipo de servicio: Background Worker.
3. Build command: `bash render-build.sh`  (instala FFmpeg con apt)
4. Start command: `python bot.py`
5. Variables de entorno obligatorias:
   - DISCORD_TOKEN: token del bot
   - DB_MODE=turso
   - TURSO_URL=libsql://botdiscordzeku-fenix7jpg.aws-us-east-1.turso.io
   - TURSO_AUTH_TOKEN: token de la base (Turso dashboard, con permisos de escritura)

6. Variables opcionales:
   - COHERE_API_KEY: para respuestas con IA al mencionar al bot
   - YT_COOKIES_FILE=/etc/secrets/youtube_cookies.txt y un Secret File con las
     cookies exportadas en formato Netscape, si /ytmp3 o /play dan bloqueos

7. Dashboard web (/panel), variables nuevas:
   - DISCORD_CLIENT_ID y DISCORD_CLIENT_SECRET: credenciales OAuth2 de la
     aplicacion del bot (portal de desarrolladores de Discord).
   - DASHBOARD_PUBLIC_URL: URL publica del servicio de Render (ej.
     https://mi-bot.onrender.com). La redirect URI a registrar en el portal es
     DASHBOARD_PUBLIC_URL + /panel/callback
   - DASHBOARD_SECRET: cadena larga y aleatoria para firmar la sesion del panel
     (si falta usa LOG_PASSWORD, y si tampoco hay, una aleatoria por proceso).
   Con el login (scope identify + guilds) el panel lista solo los servidores
   donde el usuario es administrador y el bot esta presente; desde ahi se
   editan la economia/trabajos (modo de trabajo, minijuego, turnos, sesiones
   por dia, riesgos) y los ajustes generales (bienvenida, tickets, alianzas).
   Cada guardado queda en la tabla config_audit con autor y valores.

## Notas importantes

- La base Turso es remota y persistente: aunque Render reinicie el servicio,
  el dinero/XP/configuración de los servidores no se pierde. Los catálogos
  (trabajos/enfermedades) también son tablas de la BD y se siembran solos
  en el primer arranque.
- Para crear el token de Turso: turso db tokens create <nombre-db> o desde el
  dashboard de la base, pestaña Tokens.
- Verifica la conexión antes de desplegar: `python scripts/probar_db.py`
  (con las variables de entorno cargadas) debe responder "Lectura y escritura
  de prueba: OK".
