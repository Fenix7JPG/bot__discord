# Contratos: comandos slash y botones (001-dashboard-trabajos)

## Slash commands

### /work (modificado, cogs/economia/work.py)

Rama por config del servidor (lectura fresca):

- Sin perfil: aviso "Usa /jugar para registrarte" (igual que hoy).
- Sin profesion: aviso de postularse (igual que hoy).
- Config work_mode='cooldown': flujo clasico intacto (24h, pago reducido, riesgo).
- Config work_mode='turnos' (default): abre sesion de minijuego.

Sesion de turnos (FR-001..FR-005):

1. /work crea SesionTurnos (turnos_totales = turns_per_session de config).
2. Primer turno: embed "Turno 1/N - pregunta" + View con 4 botones (Discord UI).
3. Al presionar un boton: solo el autor de la sesion puede jugar (otros: efimero);
   acierto = pago parcial + XP acumulados en la sesion; fallo = 0 y, si el trabajo
   es_riesgoso, tirada health_loss_chance -> -10 salud (aplicado al final del turno).
4. Siguiente turno hasta agotar; resumen final: total $ y XP, aciertos, bonus de racha
   (25% si perfecto), salud actual y sesiones restantes hoy.
5. Expiracion (3 min sin responder): mensaje "Sesion expirada", la sesion se libera.
6. Limite diario: si sesiones_hoy >= sessions_per_day -> aviso con hora de reinicio
   00:00 UTC, sin abrir sesion.
7. El contador (dia UTC + sesiones_hoy) se guarda AL INICIAR la sesion.

### /trabajos (modificado, cogs/economia/trabajos.py)

Lista paginada (paginacion existente se conserva) mostrando por profesion: nombre,
emoji, nivel, salario por sesion, turnos sugeridos, riesgo (Si/No) y XP requerida.

### /postularse-trabajo (modificado, cogs/economia/postularse_trabajo.py)

Igual que hoy (validacion XP, tirada lucky_chance de config del servidor en vez de la
constante 30) + aviso de que la suerte viene de la configuracion del servidor.

### /renunciar-trabajo (NUEVO, cogs/economia/renunciar_trabajo.py)

- Sin profesion: aviso.
- Con profesion: confirmacion con botones Confirmar/Cancelar (efimero, solo autor).
  Confirmar -> trabajo=None, mensaje de renuncia. Cancelar -> nada.

## Botones (interfaz, cogs/economia/vistas_trabajo.py)

- VistaTurno: 4 botones con las opciones del turno; disabled al responder; el
  callback delega en services/turnos_trabajo.
- VistaConfirmarRenuncia: Confirmar/Cancelar.

## Servicios (logica pura, testeados sin Discord)

services/turnos_trabajo.py

- `crear_sesion(config, trabajo, jugador, rng) -> dict` (pregunta 1 incluida)
- `responder_turno(sesion, indice_elegido, config, trabajo, rng) -> dict`
  (resultado del turno + estado; incluye siguiente pregunta o resumen final)
- `calcular_pago_turno(sueldo, turnos, aciertos_previos) -> int`
- `calcular_bonus(aciertos, turnos) -> int` (25% del sueldo si perfecto, 0 si no)
- `calcular_xp(sueldo, turnos, aciertos) -> int`
- `sesiones_disponibles(jugador, hoy_utc) -> int`
- `aplicar_enfermedad(salud, config, trabajo, rng) -> tuple[int, bool]`
- GestorSesiones: crear/responder/expirar (expiracion 3 min, una sesion por usuario).

services/minijuegos.py

- `generar_calculo(rng) -> dict` {tipo, texto, opciones(4), correcta(indice)}
- `generar_memoria(rng) -> dict` {tipo, texto, opciones(4), correcta(indice),
  secuencia(5)} - el embed muestra la secuencia y pregunta por la posicion N.
- `generar_pregunta(tipo, rng) -> dict` (despacho por tipo)

database/servidor_repo.py (ampliado)

- `get_economia(guild_id) -> dict` (con defaults si no hay fila)
- `set_economia(guild_id, valores: dict) -> list[dict]` (valida rangos, upsert,
  escribe auditoria, devuelve cambios [{campo, anterior, nuevo}])
- `get_auditoria(guild_id, limit=20) -> list[dict]`

database/jugadores_repo.py (ampliado): campos nuevos en 'permitidos' y
CAMPOS_INICIALES (dia_ultimo_trabajo, sesiones_hoy).
