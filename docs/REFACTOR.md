# Registro de la reorganización (2026-08-24)

Qué se hizo en el refactor y por qué. Nada se borró: todo el código viejo
vive en legacy/.

## Problemas encontrados en el estado original

1. bot_n_deprecated.py (36 KB) era un segundo bot completo monolítico que no
   podía ni importarse: hacía `from ia import IA` pero ia.py solo imprimía
   versiones de librerías. La clase IA nunca existió.
2. Duplicación total: postularse, work, stats, curarse, cat y ruleta rusa
   existían a la vez como comandos sueltos del monolito y como cogs en
   commands/.
3. Dos webservers keep-alive (webserver.py y pag.py) casi idénticos.
4. La economía usaba data.json con escritura atómica casera; la configuración
   de servidores usaba SQLite; dos mundos separados.
5. Desajustes de esquema: database.py creaba columnas welcome_channel_id /
   ticket_channel_id pero ticket_repo y welcome_repo leían columnas
   ticket_channel / welcome_channel (habrían fallado en una BD nueva).
6. datos muertos o ambiguos: Chambas.txt (lista cruda de trabajos),
   info.txt (ideas del juego), test.py (fragmento suelto de Lavalink),
   ia2.py (prueba local de llama.cpp), example.py/example2.py (cogs vacíos).
7. blackjack con bugs: view.message nunca asignado (timeout rompía) y Double
   Down sin validar fondos.
8. ruleta escribía dos veces el dinero con recargas entre medias.

## Decisiones del refactor

- Un solo entrypoint (bot.py) que carga todos los cogs de cogs/ recursivo.
- Una sola capa de datos: database/ con modo dual SQLite local / Turso remoto
  (mismo patrón HTTP Hrana ya probado en el proyecto gestor_de_tareas).
- La economía vive ahora en la BD (tabla jugadores), no en JSON. Los catálogos
  (trabajos, enfermedades) quedan como JSON porque son datos de contenido.
- Perfil global por usuario (no por servidor): el progreso acompaña al usuario.
- Esquema único consistente: guild_config con welcome_channel_id,
  ticket_category_id, alliance_channel_id, hunter_role_id, alliance_role_id.
- Chambas.txt se convirtió en datos/trabajos.json (101 puestos, slugs limpios,
  sueldos según los rangos de info.txt). Regenerable con scripts/.
- info.txt se organizó en docs/IDEAS_JUEGO.md; lo ambiguo quedó listado como
  idea pendiente en vez de inventar comportamiento.
- test.py (fragmento de Lavalink) y ia2.py (prueba llama.cpp) se conservan en
  legacy/ como referencia; no hay Lavalink en el bot nuevo.
- example/example2 se conservan en legacy/commands/utils/ como plantillas.
- El comando raidear del monolito (solo respondía "...") se dejó en legacy;
  si se quiere, es trivial re-crearlo.
