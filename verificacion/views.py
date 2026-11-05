import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from estudiantes.servicios import (
    QRNoValido,
    identificar_por_codigo,
    identificar_por_qr,
    ocultar_cedula,
    validar_codigo,
)


@login_required
def verificar(request):
    """Pantalla de verificación en vivo. Paso 1: identificación por QR (HU02) o por código escrito (HU03)."""
    return render(request, "verificacion/verificar.html")


def _identificar(datos, usuario):
    """Usa el QR leído por la cámara o, si viene 'codigo', el código escrito a mano (HU03)."""
    if "codigo" in datos:
        codigo = "".join(str(datos.get("codigo") or "").split())  # quita espacios que el docente haya escrito
        if not codigo:
            raise QRNoValido("Escriba el código de validación impreso en el carné.")
        return identificar_por_codigo(validar_codigo(codigo), usuario)
    return identificar_por_qr(datos.get("qr", ""), usuario)


@login_required
@require_POST
def identificar(request):
    """Recibe el texto del QR o el código escrito y devuelve los datos del estudiante en JSON."""
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "estado": "error", "mensaje": "Solicitud no válida."}, status=400)

    try:
        resultado = _identificar(datos, request.user)
    except QRNoValido as error:
        estado = "codigo_no_valido" if "codigo" in datos else "qr_no_valido"
        return JsonResponse({"ok": False, "estado": estado, "mensaje": str(error)}, status=400)

    carnet = resultado.carnet
    if carnet is None:  # el SGA indicó que el carné no es válido
        return JsonResponse({"ok": False, "estado": resultado.estado, "mensaje": resultado.mensaje})
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
