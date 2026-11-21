"""Textos legibles para la pantalla de auditoría (HU17), como en el prototipo."""

TABLAS = {
    "epp_m_usuario": "Usuario",
    "epp_m_rol": "Rol",
    "epp_m_laboratorio": "Laboratorio",
    "epp_m_laboratorio_epp": "Requisito EPP del laboratorio",
    "epp_m_epp": "EPP",
    "epp_m_periodo_academico": "Periodo académico",
    "epp_m_parametro": "Parámetro general",
    "epp_m_modelo_vision": "Modelo de visión",
    "epp_m_estudiante": "Estudiante",
    "epp_m_carnet_estudiantil": "Carné",
    "epp_t_validacion": "Validación",
    "epp_p_correccion_validacion": "Corrección",
    "epp_t_llamado_atencion": "Llamado de atención",
}
ACCIONES = {"INSERT": "Creación", "UPDATE": "Modificación", "DELETE": "Desactivación", "LOGIN": "Inicio de sesión",
            "NOTIFICACION": "Notificación por correo"}
CAMPOS = {
    "id_rol": "Rol", "id_laboratorio": "Laboratorio", "id_epp": "EPP", "id_estudiante": "Estudiante", "id_carnet": "Carné",
    "id_periodo": "Periodo", "id_modelo": "Modelo", "id_usuario": "Usuario", "id_usuario_registro": "Registrado por",
    "id_usuario_supervisor": "Supervisor", "activo": "Estado", "confianza_minima": "Confianza mínima", "obligatorio": "Obligatorio",
    "tiempo_estabilizacion_segundos": "Tiempo de estabilización", "estado_registro": "Estado del registro",
    "resultado_final": "Resultado final", "resultado_modelo": "Resultado del modelo", "clase_modelo": "Clase del modelo",
    "codigo_validacion": "Código del carné", "fecha_inicio": "Fecha de inicio", "fecha_fin": "Fecha de fin",
    "fecha_inicio_vigencia": "Inicio de vigencia", "fecha_fin_vigencia": "Fin de vigencia", "cedula": "Cédula",
    "descripcion": "Descripción", "ubicacion": "Ubicación", "contrasena": "Contraseña", "tipo_error": "Tipo de error",
    "valor_anterior": "Valor anterior", "valor_nuevo": "Valor nuevo", "cantidad_incidencias": "Incidencias", "correo": "Correo",
}


def tabla_texto(tabla):
    return TABLAS.get(tabla, tabla)


def accion_texto(accion):
    return ACCIONES.get(accion, accion)


def campo_texto(campo):
    return CAMPOS.get(campo, campo.replace("_", " ").capitalize())


def valor_texto(campo, valor):
    if valor is None or valor == "":
        return "sin dato"
    if campo == "activo":
        return "Activo" if valor else "Inactivo"
    if campo == "confianza_minima":
        return f"{round(float(valor) * 100)} %"
    if campo == "tiempo_estabilizacion_segundos":
        return f"{valor} s"
    if campo in ("resultado_final", "resultado_modelo"):
        return "Cumple" if valor == "conforme" else "No cumple"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if campo.startswith("id_"):
        return f"#{valor}"
    return str(valor)


def valores(datos):
    """[(campo legible, valor legible)] para mostrar los bloques Antes / Después."""
    return [(campo_texto(k), valor_texto(k, v)) for k, v in (datos or {}).items()]


def describir_cambios(evento):
    """Frases del recuadro "Qué pasó"."""
    if evento.accion == "LOGIN":
        return ["Se inició sesión. No se modificó ningún dato."]
    if evento.accion == "NOTIFICACION":
        return [evento.descripcion or "Intento de notificación por correo. No se modificó ningún dato."]
    if evento.accion == "INSERT":
        return [f"Se agregó un registro nuevo con {len(evento.datos_nuevos or {})} datos."]
    antes, despues = evento.datos_anteriores or {}, evento.datos_nuevos or {}
    if evento.accion == "DELETE" and not despues:
        return ["Se eliminó este registro."]
    frases = [
        f"{campo_texto(k)} cambió de «{valor_texto(k, antes.get(k))}» a «{valor_texto(k, despues.get(k))}»."
        for k in despues if antes.get(k) != despues.get(k)
    ]
    return frases or ["No hubo cambios en los datos."]
