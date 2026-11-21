"""Campana de notificaciones que se actualiza sola (HU15 / RF12-CA01).

La página consulta este punto al registrar una validación (al instante) y cada 10 segundos,
así el docente ve al nuevo reincidente sin recargar. Usa la misma lógica que la campana
inicial (pendientes_de_llamado) y no modifica la base de datos.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

from .reincidencia import pendientes_de_llamado


@login_required
@require_GET
def notificaciones(request):
    periodo, lista = pendientes_de_llamado()
    contexto = {"notificaciones_llamado": lista[:5], "total_notificaciones": len(lista), "periodo_notificaciones": periodo}
    return JsonResponse({
        "total": len(lista),
        "html": render_to_string("seguimiento/_campana_contenido.html", contexto, request=request),
        # Todos los pendientes (no solo los 5 visibles), para avisar cuando aparece uno nuevo.
        "estudiantes": [{"id": r.estudiante.pk, "nombre": str(r.estudiante)} for r in lista],
    })
