"""Cog /work: trabajar para ganar dinero y experiencia (cooldown de 24h)."""

import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from database import jugadores_repo
from utils import datos

COOLDOWN_HORAS = 24
DIAS_LIMITE_ENFERMEDAD = 3
SUELDO_DE_RESERVA = 50  # si el trabajo ya no esta en trabajos.json


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
    """Pago por trabajar con riesgo de enfermedad si no se respeta el cooldown."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="work",
        description="Trabaja para ganar dinero y experiencia (requiere tener un trabajo).",
    )
    async def work(self, interaction: discord.Interaction):
        """Aplica el cooldown de 24h y paga segun la rama que toque."""
        jugador = jugadores_repo.get_jugador(interaction.user.id)
        if jugador is None:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa /jugar para registrarte primero.", ephemeral=True
            )
            return

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
