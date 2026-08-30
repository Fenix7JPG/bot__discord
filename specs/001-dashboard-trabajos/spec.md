# Feature Specification: Dashboard de configuracion y trabajos estilo Nekotina

**Feature Branch**: `001-dashboard-trabajos`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "Implementar un dashboard para configurar opciones del bot, y que el sistema de trabajos sea parecido al de Nekotina (lista de profesiones con salario, turnos diarios, riesgo y requisitos; postularse y abandonar). Usar la mejor arquitectura para el bot y agregar tests."

## Clarifications

### Session 2026-08-30

- Q: Para el login del dashboard con Discord, quien crea las credenciales y donde se guardan? -> A: Login con la API de Discord (OAuth2), sin login propio; las credenciales las crea el usuario en el portal de desarrolladores y viven en variables de entorno (.env). Los datos de la cuenta vinculada (id, nombre, servidores administrados) se guardan en la base de datos (Turso en produccion).
- Q: Como responden los jugadores los turnos del minijuego de trabajo? -> A: Todo con botones nativos de Discord (respuesta a un toque, sin escribir).
- Q: Que opciones debe cubrir el dashboard en su primera version? -> A: Economia/trabajos Y tambien los ajustes existentes del bot: bienvenida, tickets y alianzas.
- Q: Que estilo visual y enfoque de frontend quieres para el dashboard? -> A: Tema oscuro propio (estilo Discord pero no generico), sin emojis en la interfaz, tipografia Elephant para titulos y Comic Sans para cuerpo, maxima rapidez y ergonomia; solo HTML, CSS y JavaScript (sin frameworks ni CDNs).
- Q: El esquema nuevo de turnos por dia reemplaza al cooldown actual de 24h entre trabajos? -> A: El modo de trabajo es configurable desde el dashboard por servidor: sesiones con turnos por dia (nuevo) o cooldown clasico de 24h (modo actual).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Turnos de trabajo estilo Nekotina (Priority: P1)

Un jugador registrado usa el comando de trabajo y el sistema le propone un minijuego
de turnos ligado a su profesion (por ejemplo acertar un calculo o elegir la opcion
correcta de memoria), todo respondido con botones nativos de Discord. Cada turno
acertado paga una parte del salario del trabajo mas experiencia; fallar un turno paga
nada de ese turno y puede tener riesgo de salud si el trabajo es riesgoso. Las sesiones
por dia estan limitadas: cuando se acaban, el jugador recibe un aviso claro y debe
esperar el reinicio diario (UTC).

**Why this priority**: Es el corazon del pedido: hoy /work paga una vez cada 24h con
una formula ciega; con turnos y minijuego el trabajo se vuelve interactivo y repetible,
que es lo que hace a Nekotina pegajosa.

**Independent Test**: Registrando un jugador de prueba y llamando al comando de trabajo
con interacciones falsas se puede jugar una sesion completa de turnos sin red ni Discord
real, verificando pagos, XP, limite diario y riesgo.

**Acceptance Scenarios**:

1. **Given** un jugador con perfil y profesion asignada, **When** usa el comando de trabajo, **Then** se le presenta un minijuego de turnos y cada acierto suma salario parcial y experiencia.
2. **Given** un jugador que acierta todos los turnos del dia, **When** intenta trabajar de nuevo el mismo dia UTC, **Then** recibe un mensaje de limite alcanzado con la hora del reinicio y no gana nada.
3. **Given** un trabajo marcado como riesgoso, **When** el jugador falla un turno, **Then** hay una probabilidad configurada de perder salud (y se informa cuanto).
4. **Given** un jugador sin profesion, **When** usa el comando de trabajo, **Then** recibe el aviso de postularse primero (sin cambio de comportamiento respecto a hoy).
5. **Given** un servidor configurado en modo cooldown clasico, **When** un jugador usa el comando de trabajo, **Then** se aplica el comportamiento actual de 24h (pago reducido y riesgo si trabaja antes de tiempo).

---

### User Story 2 - Lista de profesiones, postularse y renunciar (Priority: P1)

El jugador consulta la lista de profesiones con salario por turno, turnos diarios
exigidos, nivel de riesgo y requisitos (experiencia minima). Se postula a una
profesion eligiendola de la lista (menu interactivo o nombre), el sistema valida
requisitos (si no cumple, hay una probabilidad baja de entrar igual, como hoy) y puede
renunciar a su profesion actual cuando quiera.

**Why this priority**: La lista con datos visibles y el ciclo aplicar/leave es la otra
mitad de la experiencia Nekotina; sin esto el minijuego no sabe a que profesion sirve.

**Independent Test**: Con el catalogo sembrado se puede listar, postularse a un trabajo
que exige mas XP de la que se tiene (falla o entra con suerte), postularse a uno
alcanzable y renunciar; todo verificable con interacciones falsas.

**Acceptance Scenarios**:

1. **Given** el catalogo sembrado, **When** el jugador pide la lista de profesiones, **Then** ve nombre, salario por turno, turnos diarios, riesgo y requisito de experiencia de cada profesion.
2. **Given** un trabajo con requisito de XP, **When** el jugador con XP insuficiente se postula, **Then** es rechazado salvo tirada de suerte (probabilidad conocida) y el mensaje lo explica.
3. **Given** un jugador con profesion actual, **When** se postula a otra y es aceptado, **Then** su profesion cambia a la nueva.
4. **Given** un jugador con profesion, **When** renuncia, **Then** queda sin profesion y se lo informa.

---

### User Story 3 - Dashboard web de configuracion por servidor (Priority: P2)

Un administrador del servidor abre la pagina del dashboard (la misma web que ya sirve
el bot en su puerto), inicia sesion con Discord (OAuth2) y solo si es administrador de
un servidor donde esta el bot puede entrar a la configuracion de ese servidor. Desde
ahi ajusta opciones de economia (minijuego activo, turnos por sesion, sesiones por dia,
riesgo por fallo, probabilidad de entrada sin requisitos, modo de trabajo) y los
ajustes existentes del bot: canal de bienvenida, categoria de tickets y canal de
alianzas. Los cambios se guardan por servidor y afectan a los comandos en cuanto se
usan; cada guardado queda registrado en una auditoria con autor y valores.

**Why this priority**: Es el pedido explicito de dashboard, pero depende de las
historias 1 y 2 (configura cosas que primero deben existir).

**Independent Test**: Levantando la web del bot en un entorno de prueba con una base
temporal y un usuario simulado de staff, se puede autenticar, ver la configuracion del
servidor, cambiar valores y comprobar que los comandos usan los nuevos valores.

**Acceptance Scenarios**:

1. **Given** el dashboard abierto, **When** un admin inicia sesion con Discord, **Then** ve solo los servidores donde es administrador y el bot esta presente.
2. **Given** la pagina de configuracion de un servidor, **When** cambia los turnos diarios de 3 a 5 y guarda, **Then** el nuevo limite aplica al siguiente uso del comando de trabajo en ese servidor.
3. **Given** un usuario que NO es admin del servidor, **When** intenta abrir su configuracion, **Then** el dashboard le niega el acceso con mensaje claro.
4. **Given** valores fuera de rango (por ejemplo 99 turnos diarios o riesgo 200%), **When** se intentan guardar, **Then** el dashboard rechaza el cambio y muestra los rangos validos.
5. **Given** la seccion de ajustes del bot, **When** el admin cambia el canal de bienvenida o la categoria de tickets, **Then** los cogs correspondientes usan el nuevo valor al siguiente evento.

---

### Edge Cases

- Que pasa si el jugador tiene una profesion que ya no existe en el catalogo: el
  sistema lo avisa y le permite postularse de nuevo (no debe romper el comando).
- Que pasa si dos cambios de configuracion llegan casi al mismo tiempo: el ultimo
  guardado gana (upsert), sin estados corruptos.
- Que pasa si la sesion del dashboard expira a mitad de un guardado: se pide
  re-autenticar y no se aplica el cambio.
- Que pasa si el bot se reinicia a mitad de una sesion de turnos: la sesion se pierde
  (es efimera en memoria) pero los turnos ya cobrados del dia quedan respetados.
- Que pasa si el catalogo esta vacio (BD nueva sin sembrar): los comandos avisan en
  vez de fallar con traceback.
- Que pasa si el intercambio OAuth2 falla o el state no coincide: el dashboard muestra
  error claro y no crea sesion.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El comando de trabajo MUST ejecutar una sesion de minijuego por turnos (de 1 a N turnos, valor por configuracion del servidor) con una pregunta por turno respondida con botones nativos de Discord.
- **FR-002**: Cada turno acertado MUST pagar una fraccion del salario del trabajo (total repartido entre los turnos, con bonus por racha perfecta) mas experiencia.
- **FR-003**: Un turno fallado MUST pagar 0 de ese turno y, si el trabajo es riesgoso, aplicar una probabilidad de perdida de salud configurada por servidor.
- **FR-004**: El sistema MUST limitar la cantidad de sesiones de trabajo por jugador y dia UTC (valor por configuracion), avisando la hora del reinicio.
- **FR-005**: El sistema MUST ofrecer al menos dos tipos de minijuego para los turnos (pregunta de calculo y opcion multiple de memoria), ambos respondidos con botones nativos, seleccionable por configuracion del servidor.
- **FR-006**: MUST existir un comando de lista de profesiones con salario por turno, turnos diarios, riesgo y requisito de experiencia.
- **FR-007**: MUST existir postulacion con validacion de requisitos (XP minima; probabilidad de entrar sin cumplir, configurable por servidor) y renuncia a la profesion actual.
- **FR-008**: MUST existir un dashboard web con login por OAuth2 de Discord (credenciales DISCORD_CLIENT_ID y DISCORD_CLIENT_SECRET en variables de entorno; sin login propio) que solo de acceso a la configuracion de servidores donde el usuario es administrador y el bot esta presente. La cuenta vinculada y sus servidores administrados se guardan en la base de datos.
- **FR-009**: El dashboard MUST permitir configurar por servidor: minijuego activo, turnos por sesion, sesiones por dia, probabilidad de perdida de salud por fallo en trabajos riesgosos, probabilidad de entrada sin requisitos y modo de trabajo (sesiones por dia o cooldown clasico de 24h).
- **FR-010**: El dashboard MUST validar rangos al guardar (por ejemplo turnos 1 a 5, sesiones 1 a 10, riesgos 0 a 100%) y rechazar valores invalidos mostrando el rango.
- **FR-011**: La configuracion por servidor MUST persistir en la base de datos (upsert por servidor) y los comandos MUST leerla en cada uso (sin reiniciar el bot).
- **FR-012**: El modo cooldown clasico de 24h conserva el comportamiento actual (pago reducido y riesgo de enfermedad si se trabaja antes de tiempo); el modo por defecto para servidores sin configuracion es sesiones por dia.
- **FR-013**: Toda accion de configuracion del dashboard MUST quedar registrada con autor, servidor, valores anteriores y nuevos, y fecha ISO UTC.
- **FR-014**: Los cogs nuevos o modificados MUST seguir el patron de carga actual (archivo bajo cogs/ con setup) y la logica nueva MUST vivir en servicios/repos con tests sin Discord.
- **FR-015**: El dashboard MUST incluir tambien la edicion de los ajustes existentes por servidor: canal de bienvenida, categoria de tickets y canal de alianzas (los mismos datos que ya usa el bot), aplicando al siguiente evento sin reiniciar.
- **FR-016**: El dashboard MUST servir paginas propias en HTML/CSS/JavaScript puro (sin frameworks ni CDNs), con tema oscuro propio, sin emojis en la interfaz y con la tipografia definida (Elephant para titulos, Comic Sans para cuerpo), priorizando rapidez y ergonomia.

### Key Entities *(include if feature involves data)*

- **Profesion (trabajo)**: nombre, slug, emoji, nivel, salario por turno, turnos diarios sugeridos, riesgo (si/no), experiencia requerida. Ya existe como catalogo; se amplian atributos.
- **Perfil del jugador**: dinero, experiencia, profesion actual, salud, enfermedad, dia UTC del ultimo trabajo y sesiones hechas ese dia. Amplia el perfil existente.
- **Sesion de minijuego**: efimera (memoria), jugador, profesion, turnos totales, turno actual, aciertos, estado. No persiste.
- **Configuracion de servidor (economia)**: minijuego activo, modo de trabajo, turnos por sesion, sesiones por dia, riesgo de salud por fallo (%), probabilidad de entrada sin requisitos (%). Una fila por servidor.
- **Configuracion de servidor (general)**: canal de bienvenida, categoria de tickets, canal de alianzas (ya existe como guild_config; el dashboard la edita).
- **Registro de auditoria de configuracion**: servidor, autor, campo, valor anterior, valor nuevo, fecha ISO UTC.
- **Cuenta del dashboard**: usuario de Discord vinculado via OAuth2 (id, nombre), con registro de servidores donde administra; persiste en la base de datos.
- **Sesion de dashboard**: efimera (cookie firmada), usuario Discord, servidores administrados, caducidad.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un jugador completo puede registrarse, postularse a una profesion y jugar una sesion de turnos completa en menos de 2 minutos desde Discord.
- **SC-002**: El 100% de las reglas nuevas (pagos por turno, limites diarios, riesgo, validaciones de config, permisos del dashboard) esta cubierta por tests automatizados que corren sin red ni Discord real.
- **SC-003**: Un cambio de configuracion hecho en el dashboard aplica al siguiente uso del comando correspondiente en menos de 5 segundos (lectura fresca por uso).
- **SC-004**: La suite completa previa (82 tests) sigue verde: ningun comando existente rompe, salvo el cambio de modo de trabajo explicitado en FR-012.

## Assumptions

- El dashboard vive en el proceso Flask existente (webserver.py) del Bot: no hay un
  servicio web nuevo separado.
- Login del dashboard por OAuth2 de Discord usando credenciales propias del bot
  (DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET en .env o variables de Render); sin
  sistema de login propio.
- Sin backend extra de tareas programadas: el limite diario usa fecha UTC (YYYY-MM-DD)
  comparada al vuelo; no hay un job de medianoche.
- El catalogo actual de ~101 profesiones se reutiliza tal cual, agregando atributos
  (turnos sugeridos, riesgo) con valores derivados de su nivel.
- Los minijuegos de v1 son de botones nativos de Discord (calculadora y memoria);
  minijuegos graficos quedan fuera de alcance.
- La configuracion de economia es por servidor; los valores por defecto son: modo
  sesiones por dia, 3 turnos por sesion, 2 sesiones por dia, 35% de perdida de salud
  por fallo en trabajos riesgosos, 30% de entrada sin requisitos.
- La interfaz del dashboard usa solo fuentes instaladas en el equipo del usuario
  (Elephant y Comic Sans vienen con Windows); sin descargar fuentes.
