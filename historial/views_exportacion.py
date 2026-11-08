"""Botón "Exportar CSV" de Registros e Incidencias (HU11 / RF10)."""
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from .exportacion import respuesta_csv
from .filtros import filtrar_validaciones, leer_filtros


@login_required
@require_GET
def registros_csv(request):
    """Registros con los filtros actuales (laboratorio, periodo, fechas, estudiante y resultado)."""
    validaciones = filtrar_validaciones(leer_filtros(request.GET))
    return respuesta_csv(validaciones, "registros")


@login_required
@require_GET
def incidencias_csv(request):
    """Solo intentos "No cumple" (pestaña Intentos no conformes), con los filtros actuales."""
    validaciones = filtrar_validaciones(leer_filtros(request.GET), solo_incidencias=True)
    return respuesta_csv(validaciones, "incidencias")
