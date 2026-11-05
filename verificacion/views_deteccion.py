"""Punto de acceso web del servicio de detección (TK07)."""
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from . import deteccion

logger = logging.getLogger(__name__)
TAMANO_MAXIMO = 2 * 1024 * 1024  # 2 MB por fotograma; así Django lo mantiene en memoria y no en disco


def _error(estado, mensaje, codigo):
    return JsonResponse({"ok": False, "estado": estado, "mensaje": mensaje}, status=codigo)


@login_required
@require_POST
def detectar(request):
    """Recibe un fotograma en el campo 'fotograma' y devuelve los EPP detectados en JSON."""
    archivo = request.FILES.get("fotograma")
    if archivo is None:
        return _error("sin_fotograma", "No se recibió ningún fotograma.", 400)
    if archivo.size > TAMANO_MAXIMO:
        return _error("fotograma_grande", "El fotograma supera el tamaño permitido.", 400)

    try:
        resultado = deteccion.detectar(archivo.read())
    except deteccion.ImagenNoValida as error:
        return _error("imagen_no_valida", str(error), 400)
    except deteccion.DeteccionNoDisponible as error:
        return _error("servicio_no_disponible", str(error), 503)
    except Exception:  # cualquier otra falla del modelo: error controlado (TK07-CA04, RNF10)
        logger.exception("Falla del servicio de detección")
        return _error("servicio_no_disponible", "El servicio de detección no respondió. Intente de nuevo.", 503)

    return JsonResponse({"ok": True, **resultado})
