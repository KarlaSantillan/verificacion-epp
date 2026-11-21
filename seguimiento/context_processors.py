from .reincidencia import pendientes_de_llamado


def notificaciones(request):
    """Campana de la barra superior: estudiantes que requieren llamado de atención (RF12-CA01)."""
    usuario = getattr(request, "user", None)
    if not usuario or not usuario.is_authenticated:
        return {}
    periodo, lista = pendientes_de_llamado()
    return {
        "notificaciones_llamado": lista[:5],
        "total_notificaciones": len(lista),
        "periodo_notificaciones": periodo,
        "ids_notificaciones": ",".join(str(r.estudiante.pk) for r in lista),  # para que campana.js detecte los nuevos
    }
