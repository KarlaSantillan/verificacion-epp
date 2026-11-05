"""Resultado de cumplimiento al terminar la estabilización (HU07)."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from configuracion.models import Laboratorio

from .evaluacion import SinRequisitos, evaluar


def _error(mensaje, codigo=400):
    return JsonResponse({"ok": False, "mensaje": mensaje}, status=codigo)


@login_required
@require_POST
def evaluar_cumplimiento(request):
    """Recibe {laboratorio, confianzas} y devuelve "Cumple" o "No cumple" con los faltantes."""
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("Solicitud no válida.")

    laboratorio = Laboratorio.objects.filter(pk=datos.get("laboratorio"), activo=True).first()
    if laboratorio is None:
        return _error("El laboratorio no existe o está inactivo.")
    confianzas = datos.get("confianzas")
    if not isinstance(confianzas, dict):
        return _error("Faltan las confianzas detectadas.")

    try:
        evaluacion = evaluar(laboratorio, confianzas)
    except SinRequisitos as error:
        return _error(str(error))

    return JsonResponse(
        {
            "ok": True,
            "resultado": "conforme" if evaluacion.cumple else "no_conforme",
            "etiqueta": "Cumple" if evaluacion.cumple else "No cumple",
            "faltantes": evaluacion.faltantes,
            "detalles": [
                {
                    "epp": d.epp,
                    "clase": d.clase,
                    "requerido": d.requerido,
                    "confianza": float(d.confianza) if d.confianza is not None else None,
                    "umbral": float(d.umbral),
                    "detectado": d.detectado,
                }
                for d in evaluacion.detalles
            ],
        }
    )
