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

## Notas importantes

- El plan gratuito de Render duerme el servicio por inactividad; el Flask del
  keep_alive responde los pings pero no impide el sleep de un worker. Si el
  bot se desconecta mucho, considera un plan pago o un cron externo que haga
  ping al health check.
- La base Turso es remota y persistente: aunque Render reinicie el servicio,
  el dinero/XP/configuración de los servidores no se pierde.
- Para crear el token de Turso: turso db tokens create <nombre-db> o desde el
  dashboard de la base, pestaña Tokens.
- Verifica la conexión antes de desplegar: `python scripts/probar_db.py`
  (con las variables de entorno cargadas) debe responder "Lectura y escritura
  de prueba: OK".
