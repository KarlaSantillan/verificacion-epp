from django.urls import NoReverseMatch, reverse

# (nombre, icono de Bootstrap Icons, nombre de la URL). None = pantalla aún no construida.
MENU_OPERACION = [
    ("Inicio", "grid-1x2", "core:inicio"),
    ("Verificación en vivo", "camera-video", "verificacion:verificar"),  # HU02/HU06 (Leo)
    ("Registros", "journal-text", "historial:registros"),  # HU10 (Karla)
    ("Carnés pendientes", "person-exclamation", "estudiantes:pendientes"),  # HU05 (Karla)
    ("Incidencias", "exclamation-triangle", "historial:incidencias"),  # HU10 / HU15
    ("Prácticas", "clipboard-data", "historial:practicas"),  # resumen de prácticas (tutoría)
    ("Ayuda", "question-circle", "core:ayuda"),
]

MENU_ADMINISTRACION = [
    ("Laboratorios", "building", "administracion:laboratorios"),
    ("Catálogo EPP", "shield-check", "administracion:catalogo"),
    ("Estudiantes y carnés", "person-vcard", "administracion:estudiantes"),
    ("Usuarios y roles", "people", "administracion:usuarios"),
    ("Periodos académicos", "calendar3", "administracion:periodos"),
    ("Parámetros generales", "sliders", "administracion:parametros"),
    ("Modelo de visión", "cpu", "administracion:modelos"),
    ("Auditoría", "clipboard2-pulse", "administracion:auditoria"),  # HU17
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
    operacion = _items(request, MENU_OPERACION)
    administracion = _items(request, MENU_ADMINISTRACION) if es_admin else []
    return {
        "menu_operacion": operacion,
        "menu_administracion": administracion,
        # Asistente de voz: solo puede abrir las secciones que el rol ve en su menú (solo navegación, sin modificar datos).
        "voz_secciones": [{"nombre": i["nombre"], "url": i["url"]} for i in operacion + administracion if i["url"]],
        "voz_secciones_admin": [nombre for nombre, _, _ in MENU_ADMINISTRACION],
        "es_administrador": es_admin,
        "rol_etiqueta": "Administrador" if es_admin else "Docente/Encargado",
        "usuario_iniciales": iniciales,
    }
