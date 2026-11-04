import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from estudiantes.servicios import QRNoValido, identificar_por_qr, ocultar_cedula


@login_required
def verificar(request):
    """Pantalla de verificación en vivo. Por ahora: paso 1, identificación por QR (HU02)."""
    return render(request, "verificacion/verificar.html")


@login_required
@require_POST
def identificar(request):
    """Recibe el texto leído del QR y devuelve los datos del estudiante en JSON."""
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "estado": "error", "mensaje": "Solicitud no válida."}, status=400)

    try:
        resultado = identificar_por_qr(datos.get("qr", ""), request.user)
    except QRNoValido as error:
        return JsonResponse({"ok": False, "estado": "qr_no_valido", "mensaje": str(error)}, status=400)

    carnet = resultado.carnet
    estudiante = carnet.estudiante
    return JsonResponse(
        {
            "ok": resultado.permite_verificar,
            "estado": resultado.estado,
            "mensaje": resultado.mensaje,
            "carnet": {
                "id": carnet.id_carnet,
                "codigo": carnet.codigo_validacion,
                "estado_registro": carnet.get_estado_registro_display(),
                "fin_vigencia": carnet.fecha_fin_vigencia.isoformat() if carnet.fecha_fin_vigencia else None,
            },
            "estudiante": {
                "nombre": str(estudiante),
                "cedula": ocultar_cedula(estudiante.cedula),
                "carrera": estudiante.carrera,
                "nivel": estudiante.nivel,
            },
        }
    )
