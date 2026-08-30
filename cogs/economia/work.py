"""Cog /work: trabajar con turnos estilo Nekotina o cooldown clasico.

El modo lo decide la configuracion de economia del servidor
(server_economy_config.work_mode, editable desde el dashboard):
- 'turnos' (default): sesion de minijuego con botones, pagos por acierto,
  limite de sesiones por dia UTC y riesgo de salud en trabajos riesgosos.
- 'cooldown': el flujo historico de 24 horas (se conserva intacto).

La logica de turnos vive en services/turnos_trabajo; este cog solo
interpreta interacciones, guarda el contador diario y edita mensajes.
"""

import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.economia.vistas_trabajo import VistaTurno
from database import jugadores_repo, servidor_repo
from services import turnos_trabajo
from utils import datos

COOLDOWN_HORAS = 24
DIAS_LIMITE_ENFERMEDAD = 3
SUELDO_DE_RESERVA = 50  # si el trabajo ya no esta en el catalogo (modo cooldown)


def _ahora_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parsear_fecha(valor):
    """Convierte una fecha ISO a datetime con zona; None si es invalida."""
    if not valor:
        return None
    try:
        fecha = datetime.fromisoformat(str(valor))
    except ValueError:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha


class Work(commands.Cog):
    """Pago por trabajar: sesiones de turnos (default) o cooldown de 24h."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gestor = turnos_trabajo.GestorSesiones()

    # ------------------------------------------------------------------
    # Comando principal
    # ------------------------------------------------------------------

    @app_commands.command(
        name="work",
        description="Trabaja para ganar dinero y experiencia (requiere tener un trabajo).",
    )
    async def work(self, interaction: discord.Interaction):
        """Enruta al modo de trabajo configurado para el servidor."""
        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

        if interaction.guild is not None:
            config = servidor_repo.get_economia(interaction.guild.id)
        else:
            config = dict(servidor_repo.ECONOMIA_DEFAULTS)

        if config.get("work_mode") == "cooldown":
            await self._work_cooldown(interaction, jugador)
        else:
            await self._work_turnos(interaction, jugador, config)

    # ------------------------------------------------------------------
    # Modo turnos (estilo Nekotina)
    # ------------------------------------------------------------------

    async def _work_turnos(self, interaction, jugador, config):
        """Abre una sesion de minijuego si el jugador tiene turnos hoy."""
        slug = jugador.get("trabajo")
        if not slug:
            await interaction.response.send_message(
                "❌ No tienes un trabajo asignado. Usa /postularse-trabajo para conseguir uno.",
                ephemeral=True,
            )
            return

        job = datos.buscar_trabajo(slug)
        if job is None:
            await interaction.response.send_message(
                "⚠️ Tu profesion guardada (" + str(slug) + ") ya no existe en el catalogo."
                " Postulate de nuevo con /postularse-trabajo.",
                ephemeral=True,
            )
            return

        hoy = turnos_trabajo.hoy_utc()
        maximas = int(config.get("sessions_per_day", 2) or 2)
        if turnos_trabajo.sesiones_disponibles(jugador, hoy, maximas) <= 0:
            hechas = self._hechas_hoy(jugador, hoy)
            await interaction.response.send_message(
                "⏰ Llegaste al limite de hoy ("
                + str(hechas)
                + "/"
                + str(maximas)
                + " sesiones). Vuelve despues de las 00:00 UTC para un nuevo dia.",
                ephemeral=True,
            )
            return

        sesion = self.gestor.crear(interaction.user.id, config, job, random)

        # El contador diario se guarda AL INICIAR la sesion
        hechas = self._hechas_hoy(jugador, hoy)
        jugadores_repo.actualizar_campos(
            jugador["user_id"],
            {"dia_ultimo_trabajo": hoy, "sesiones_hoy": hechas + 1},
        )

        vista = VistaTurno(self, interaction.user.id, sesion["pregunta_actual"])
        await interaction.response.send_message(
            "Sesion de trabajo como **"
            + sesion["nombre_trabajo"]
            + "** (turno 1 de "
            + str(sesion["turnos_totales"])
            + ")\n\n"
            + sesion["pregunta_actual"]["texto"],
            view=vista,
        )

    @staticmethod
    def _hechas_hoy(jugador: dict, hoy: str) -> int:
        """Sesiones ya contadas hoy (0 si el ultimo dia guardado es otro)."""
        if jugador.get("dia_ultimo_trabajo") != hoy:
            return 0
        return int(jugador.get("sesiones_hoy", 0) or 0)

    async def procesar_presion(self, interaction: discord.Interaction, indice: int):
        """Procesa la presion de un boton de la sesion propia del usuario."""
        user_id = interaction.user.id
        sesion = self.gestor.obtener(user_id)
        if sesion is None:
            self.gestor.liberar(user_id)
            await interaction.response.edit_message(
                content="Sesion expirada. Usa /work para empezar otra.", view=None
            )
            return

        resultado = self.gestor.responder(user_id, indice, random)
        if resultado is None:
            await interaction.response.edit_message(
                content="Sesion expirada. Usa /work para empezar otra.", view=None
            )
            return

        if not resultado["final"]:
            await self._mostrar_siguiente_turno(interaction, sesion, resultado)
            return

        await self._cerrar_sesion(interaction, sesion, resultado)

    async def _mostrar_siguiente_turno(self, interaction, sesion, resultado):
        """Edita el mensaje con el feedback y la pregunta del proximo turno."""
        if resultado["acerto"]:
            feedback = (
                "Correcto: +$"
                + str(resultado["pago"])
                + " y +"
                + str(resultado["xp"])
                + " XP."
            )
        else:
            feedback = "Incorrecto."
            if resultado["perdio_salud"]:
                feedback = feedback + " El esfuerzo te paso factura: perderas 10 de salud."

        pregunta = sesion["pregunta_actual"]
        vista = VistaTurno(self, interaction.user.id, pregunta)
        await interaction.response.edit_message(
            content="Turno "
            + str(sesion["turno_actual"])
            + " de "
            + str(sesion["turnos_totales"])
            + "\n\n"
            + pregunta["texto"]
            + "\n\n"
            + feedback,
            view=vista,
        )

    async def _cerrar_sesion(self, interaction, sesion, resultado):
        """Aplica pagos, XP y salud del resumen y muestra el resultado final."""
        resumen = resultado["resumen"]
        user_id = interaction.user.id

        jugador = jugadores_repo.get_jugador(user_id)
        dinero = int(jugador.get("dinero", 0) or 0)
        experiencia = int(jugador.get("experiencia", 0) or 0)
        salud = int(jugador.get("salud", 100) or 0)

        campos = {
            "dinero": dinero + int(resumen["total"]),
            "experiencia": experiencia + int(resumen["xp"]),
            "salud": max(0, salud - int(resumen.get("salud_perdida", 0))),
        }

        # Limpieza de enfermedad vieja (misma regla que el modo cooldown)
        enfermedad = jugador.get("enfermedad")
        fecha_enf = _parsear_fecha(jugador.get("fecha_enfermedad"))
        if enfermedad and fecha_enf is not None:
            if datetime.now(tz=timezone.utc) - fecha_enf > timedelta(
                days=DIAS_LIMITE_ENFERMEDAD
            ):
                campos["enfermedad"] = None
                campos["fecha_enfermedad"] = None

        jugadores_repo.actualizar_campos(user_id, campos)

        hoy = turnos_trabajo.hoy_utc()
        maximas = int(sesion["config"].get("sessions_per_day", 2) or 2)
        hechas = self._hechas_hoy(jugador, hoy)
        restantes = max(0, maximas - hechas)

        lineas = [
            "Sesion terminada como **" + sesion["nombre_trabajo"] + "**",
            "Aciertos: **"
            + str(resumen["aciertos"])
            + " de "
            + str(resumen["turnos"])
            + "**",
            "Ganancia: **$" + str(resumen["total"]) + "**",
        ]
        if int(resumen["bonus"]) > 0:
            lineas.append("Bonus por racha perfecta: **+$" + str(resumen["bonus"]) + "**")
        lineas.append("Experiencia: **+" + str(resumen["xp"]) + " XP**")
        if int(resumen.get("salud_perdida", 0)) > 0:
            lineas.append(
                "Salud: **-"
                + str(resumen["salud_perdida"])
                + "** (salud actual "
                + str(campos["salud"])
                + "/100)"
            )
        lineas.append(
            "Sesiones restantes hoy: **" + str(restantes) + " de " + str(maximas) + "**"
        )

        await interaction.response.edit_message(
            content="\n".join(lineas), view=None
        )

    # ------------------------------------------------------------------
    # Modo cooldown clasico (comportamiento historico, se conserva)
    # ------------------------------------------------------------------

    async def _work_cooldown(self, interaction, jugador):
        """Flujo historico: pago cada 24h, reducido y con riesgo si se anticipa."""
        slug = jugador.get("trabajo")
        if not slug:
            await interaction.response.send_message(
                "❌ No tienes un trabajo asignado. Usa /postularse-trabajo para conseguir uno.",
                ephemeral=True,
            )
            return

        job = datos.buscar_trabajo(slug)
        if job is not None:
            sueldo = datos.sueldo_base(job)
            requerida = datos.experiencia_requerida(job)
        else:
            # El trabajo desaparecio del catalogo; se paga el sueldo de reserva.
            sueldo = SUELDO_DE_RESERVA
            requerida = 0

        ahora = datetime.now(tz=timezone.utc)
        ultima = _parsear_fecha(jugador.get("fecha_trabajo"))
        horas = None if ultima is None else (ahora - ultima).total_seconds() / 3600.0

        dinero = int(jugador.get("dinero", 0) or 0)
        experiencia = int(jugador.get("experiencia", 0) or 0)

        # La fecha_trabajo siempre se guarda, gane o pierda el jugador.
        campos = {"fecha_trabajo": _ahora_iso()}

        if horas is None or horas >= COOLDOWN_HORAS:
            await self._trabajo_completo(interaction, jugador, campos, slug, sueldo, requerida, dinero, experiencia)
        else:
            await self._trabajo_anticipado(
                interaction, jugador, campos, slug, sueldo, requerida, dinero, experiencia, horas
            )

    async def _trabajo_completo(self, interaction, jugador, campos, slug, sueldo, requerida, dinero, experiencia):
        """Rama normal: pasaron las 24h o es el primer trabajo."""
        pago = max(1, int(sueldo * random.uniform(0.9, 1.3)))
        xp = random.randint(5, 20) + requerida // 2

        # Una enfermedad vieja (mas de 3 dias) se limpia al trabajar.
        enfermedad = jugador.get("enfermedad")
        fecha_enfermedad = jugador.get("fecha_enfermedad")
        fecha_enf = _parsear_fecha(fecha_enfermedad)
        if enfermedad and fecha_enf is not None:
            if datetime.now(tz=timezone.utc) - fecha_enf > timedelta(days=DIAS_LIMITE_ENFERMEDAD):
                enfermedad = None
                fecha_enfermedad = None

        campos["dinero"] = dinero + pago
        campos["experiencia"] = experiencia + xp
        campos["enfermedad"] = enfermedad
        campos["fecha_enfermedad"] = fecha_enfermedad
        jugadores_repo.actualizar_campos(jugador["user_id"], campos)

        await interaction.response.send_message(
            "✅ Trabajaste como **"
            + str(slug)
            + "** y ganaste **$"
            + str(pago)
            + "** y **"
            + str(xp)
            + " XP**.\nDinero actual: **$"
            + str(campos["dinero"])
            + "** - Experiencia total: **"
            + str(campos["experiencia"])
            + "**.\n🔸 Vuelve en ~24 horas para el siguiente /work."
        )

    async def _trabajo_anticipado(
        self, interaction, jugador, campos, slug, sueldo, requerida, dinero, experiencia, horas
    ):
        """Rama de cansancio: pago reducido y riesgo de enfermarse."""
        hazard = max(5, min(45, int((COOLDOWN_HORAS - horas) * 45 / COOLDOWN_HORAS)))
        roll = random.randint(1, 100)

        if roll <= hazard:
            await self._enfermar(interaction, jugador, campos, dinero, experiencia, requerida, horas, hazard)
        else:
            pago = max(1, sueldo // 2)
            xp = max(1, (random.randint(5, 20) + requerida // 2) // 2)
            campos["dinero"] = dinero + pago
            campos["experiencia"] = experiencia + xp
            jugadores_repo.actualizar_campos(jugador["user_id"], campos)

            await interaction.response.send_message(
                "💼 Trabajaste pero aún no han pasado 24 horas desde tu último /work ("
                + str(round(horas, 1))
                + "h). El pago se reduce por cansancio: **$"
                + str(pago)
                + "** y **"
                + str(xp)
                + " XP**.\n🔸 Riesgo de enfermedad en este intento: **"
                + str(hazard)
                + "%**. ¡Ten cuidado!"
            )

    async def _enfermar(self, interaction, jugador, campos, dinero, experiencia, requerida, horas, hazard):
        """El jugador se enferma: pierde salud, paga atencion medica y gana poca XP."""
        enfermedades = datos.obtener_enfermedades()
        if not enfermedades:
            await interaction.response.send_message(
                "❌ No hay catálogo de enfermedades cargado. Avisa a un administrador.", ephemeral=True
            )
            return

        elegida = random.choice(enfermedades)
        perdida = int(elegida.get("health_loss", 5))
        nombre = str(elegida.get("name") or elegida.get("slug") or "enfermedad")

        salud_actual = int(jugador.get("salud", 100) or 0)
        nueva_salud = max(0, salud_actual - perdida)
        gasto_medico = random.randint(0, max(0, dinero // 10))  # hasta 10% del dinero
        xp_ganada = max(1, (random.randint(5, 20) + requerida // 2) // 4)

        campos["salud"] = nueva_salud
        campos["enfermedad"] = nombre
        campos["fecha_enfermedad"] = _ahora_iso()
        campos["dinero"] = dinero - gasto_medico
        campos["experiencia"] = experiencia + xp_ganada
        jugadores_repo.actualizar_campos(jugador["user_id"], campos)

        await interaction.response.send_message(
            "🤒 Trabajaste demasiado pronto ("
            + str(round(horas, 1))
            + "h desde tu último /work) y el esfuerzo te pasó factura (riesgo "
            + str(hazard)
            + "%).\nTe dio **"
            + nombre
            + "**: pierdes **"
            + str(perdida)
            + "** de salud y gastas **$"
            + str(gasto_medico)
            + "** en atención.\nSolo ganaste **"
            + str(xp_ganada)
            + " XP**. Salud actual: **"
            + str(nueva_salud)
            + "/100**.\n🔸 Consejo: espera 24 horas entre trabajos y usa /curarse si te sientes mal."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Work(bot))
