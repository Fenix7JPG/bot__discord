# Quickstart: validacion de la feature 001-dashboard-trabajos

## Prerequisitos

- Python 3.14 del sistema: C:/Users/USER/AppData/Local/Python/pythoncore-3.14-64/python.exe
- Trabajar desde la raiz del proyecto con PYTHONPATH limpio.
- Para el dashboard con OAuth real: DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET y
  DASHBOARD_PUBLIC_URL en .env (redirect URI en el portal:
  DASHBOARD_PUBLIC_URL + /panel/callback). Sin credenciales, la suite de tests igual
  cubre auth con OAuth simulado.

## 1. Suite completa (sin red ni Discord)

```
cd D:/Proy_Github/bot__discord
env -u PYTHONPATH "C:/Users/USER/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -q
```

Esperado: todos los tests previos (82) + los nuevos de la feature en verde.

## 2. Carga real de cogs (como haria bot.py)

```
env -u PYTHONPATH "C:/Users/USER/AppData/Local/Python/pythoncore-3.14-64/python.exe" scripts/verificar_cogs.py
```

Esperado: todos los cogs cargan, incluidos los nuevos (renunciar_trabajo).

## 3. Flujo de turnos con interacciones falsas

Los tests test_work.py y test_turnos.py ejercitan: crear sesion, responder turnos con
botones falsos, limite diario, riesgo al fallar, modo cooldown clasico. Ejecutar solo:

```
env -u PYTHONPATH "C:/Users/USER/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/test_turnos.py tests/test_work.py -q
```

Esperado: verde. Casos cubiertos: pago por acierto + XP, bonus racha perfecta,
limite de sesiones con aviso de reinicio 00:00 UTC, perdida de salud en trabajos
riesgosos (rng controlado), sesion expirada, modo cooldown intacto.

## 4. Dashboard sin Discord real (test_client de Flask)

```
env -u PYTHONPATH "C:/Users/USER/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/test_dashboard_auth.py tests/test_dashboard_api.py -q
```

Esperado: verde. Casos cubiertos: login/callback con OAuth simulado (state invalido
rechazado), solo guilds admin+bot listados, guardado de config con validacion de
rangos, auditoria escrita, 403 para no-admin, 401 sin sesion, OAuth fallido -> error
sin sesion.

## 5. Prueba manual del dashboard (opcional, con credenciales)

```
cd D:/Proy_Github/bot__discord
env -u PYTHONPATH "C:/Users/USER/AppData/Local/Python/pythoncore-3.14-64/python.exe" scripts/probar_dashboard.py
```

Abre la app Flask con la config del .env y queda sirviendo en
http://localhost:5000/panel. Validar a mano: boton de login, redirige a Discord,
vuelve al panel con la lista de servidores donde eres admin y el bot esta; editar
valores (prueba un valor fuera de rango: debe rechazar sin guardar) y ver la
auditoria reflejada.

## 6. Despliegue (produccion)

- Variables nuevas en Render: DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET,
  DASHBOARD_PUBLIC_URL (URL del servicio), DASHBOARD_SECRET (cadena larga aleatoria).
- Agregar la redirect URI en el portal de desarrolladores de Discord
  (DASHBOARD_PUBLIC_URL + /panel/callback).
- El resto del despliegue no cambia (ver docs/DESPLIEGE_RENDER.md).
