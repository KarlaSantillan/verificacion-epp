from django.urls import NoReverseMatch, reverse

# (nombre, icono de Bootstrap Icons, nombre de la URL). None = pantalla aún no construida.
MENU_OPERACION = [
    ("Inicio", "grid-1x2", "core:inicio"),
    ("Verificación en vivo", "camera-video", None),  # HU02/HU06 (Leo)
    ("Registros", "journal-text", None),  # HU10
    ("Incidencias", "exclamation-triangle", None),  # HU10 / HU15
    ("Ayuda", "question-circle", None),
]

# Por ahora la administración usa el panel de Django (HU12, HU13, HU17).
MENU_ADMINISTRACION = [
    ("Laboratorios", "building", "admin:configuracion_laboratorio_changelist"),
    ("Catálogo EPP", "shield-check", "admin:configuracion_epp_changelist"),
    ("Estudiantes y carnés", "person-vcard", "admin:estudiantes_estudiante_changelist"),
    ("Usuarios y roles", "people", "admin:usuarios_usuario_changelist"),
    ("Periodos académicos", "calendar3", "admin:configuracion_periodoacademico_changelist"),
    ("Parámetros generales", "sliders", "admin:configuracion_parametro_changelist"),
    ("Modelo de visión", "cpu", "admin:configuracion_modelovision_changelist"),
    ("Auditoría", "clipboard2-pulse", "admin:auditoria_auditoria_changelist"),
]


def _items(request, lista):
    resultado = []
    for nombre, icono, nombre_url in lista:
        url = None
        if nombre_url:
            try:
                url = reverse(nombre_url)
            except NoReverseMatch:
                url = None
        resultado.append(
            {
                "nombre": nombre,
                "icono": icono,
                "url": url,
                "activo": bool(url) and (request.path == url or (url != "/" and request.path.startswith(url))),
            }
        )
    return resultado


def menu(request):
    """Menú lateral según el rol del usuario (HU01-CA01)."""
    usuario = getattr(request, "user", None)
    if not usuario or not usuario.is_authenticated:
        return {}
    es_admin = usuario.es_administrador
    iniciales = f"{(usuario.nombres or ' ')[0]}{(usuario.apellidos or ' ')[0]}".strip().upper()
    return {
        "menu_operacion": _items(request, MENU_OPERACION),
        "menu_administracion": _items(request, MENU_ADMINISTRACION) if es_admin else [],
        "es_administrador": es_admin,
        "rol_etiqueta": "Administrador" if es_admin else "Docente/Encargado",
        "usuario_iniciales": iniciales,
    }
