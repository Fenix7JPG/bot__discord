"""Lectura, validacion y guardado de la configuracion por servidor.

Junta la config de economia (server_economy_config) y la general
(guild_config), valida TODO antes de escribir y deja auditoria.
"""

from database import servidor_repo

# Campos de guild_config editables desde el panel (ids de canales/roles)
CAMPOS_GENERALES = (
    "welcome_channel_id",
    "ticket_category_id",
    "alliance_channel_id",
    "hunter_role_id",
    "alliance_role_id",
)


def obtener_vista_config(guild_id: int) -> dict:
    """Config completa del servidor para pintar el formulario del panel."""
    economia = servidor_repo.get_economia(guild_id)
    general = {}
    for campo in CAMPOS_GENERALES:
        general[campo] = servidor_repo.get_config(guild_id, campo)
    auditoria = servidor_repo.get_auditoria(guild_id)
    return {"economia": economia, "general": general, "auditoria": auditoria}


def _validar_id(valor, campo: str):
    """Id de canal/rol: entero positivo o vacio (que limpia el ajuste)."""
    if valor is None or valor == "":
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValueError(campo + " debe ser un id numerico o vacio para limpiar")
    if numero <= 0:
        raise ValueError(campo + " debe ser un id positivo o vacio para limpiar")
    return numero


def guardar_config(guild_id: int, actor_id, actor_name: str, cuerpo: dict) -> dict:
    """Valida y aplica cambios de economia y/o general para un servidor.

    Devuelve {"cambios": [...], "auditoria": [...]}. Lanza ValueError con
    TODOS los campos invalidos detectados y sin escribir nada.
    """
    if not isinstance(cuerpo, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON")

    errores: list[str] = []
    economia_cuerpo = {}
    general_cuerpo = {}

    for campo, valor in cuerpo.items():
        if campo in servidor_repo.CAMPOS_ECONOMIA:
            economia_cuerpo[campo] = valor
        elif campo in CAMPOS_GENERALES:
            general_cuerpo[campo] = valor
        else:
            errores.append("campo desconocido: " + str(campo))

    # Validar la parte general completa antes de escribir nada
    general_validado: dict[str, int | None] = {}
    for campo, valor in general_cuerpo.items():
        try:
            general_validado[campo] = _validar_id(valor, campo)
        except ValueError as e:
            errores.append(str(e))

    if errores:
        raise ValueError(" / ".join(errores))

    # Aplicar: economia valida sus rangos y audita; luego general con auditoria
    cambios: list[dict] = []
    if economia_cuerpo:
        cambios.extend(
            servidor_repo.set_economia(guild_id, economia_cuerpo, actor_id, actor_name)
        )

    for campo, valor in general_validado.items():
        anterior = servidor_repo.get_config(guild_id, campo)
        if anterior == valor:
            continue
        servidor_repo.set_config(guild_id, campo, valor)
        servidor_repo.registrar_cambio(
            guild_id, actor_id, actor_name, campo, anterior, valor
        )
        cambios.append({"campo": campo, "anterior": anterior, "nuevo": valor})

    return {"cambios": cambios, "auditoria": servidor_repo.get_auditoria(guild_id)}
