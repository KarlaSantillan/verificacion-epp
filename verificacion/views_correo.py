"""Registro del correo institucional del estudiante desde la verificación (HU16: notificación del llamado).

El SGA no entrega el correo, así que el docente lo escribe una sola vez, cuando el estudiante no lo tiene.
Si ya existe, solo se cambia desde Administración → Estudiantes y carnés.
"""
import json

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from estudiantes.forms import validar_correo_unemi
from estudiantes.models import Estudiante
from estudiantes.servicios import ocultar_correo


@login_required
@require_POST
def guardar_correo(request):
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "mensaje": "Solicitud no válida."}, status=400)

    estudiante = Estudiante.objects.filter(pk=datos.get("estudiante"), activo=True).first()
    if estudiante is None:
        return JsonResponse({"ok": False, "mensaje": "Estudiante no encontrado."}, status=404)
    if estudiante.correo:
        return JsonResponse(
            {"ok": False, "mensaje": "El estudiante ya tiene un correo registrado. Para cambiarlo, use Estudiantes y carnés."},
            status=409,
        )
    try:
        correo = validar_correo_unemi(datos.get("correo"))
    except forms.ValidationError as error:
        return JsonResponse({"ok": False, "mensaje": error.messages[0]}, status=400)
    if not correo:
        return JsonResponse({"ok": False, "mensaje": "Escriba el correo institucional del estudiante."}, status=400)

    estudiante.correo = correo
    estudiante.save(update_fields=["correo", "fecha_actualizacion"])  # la auditoría registra el cambio
    return JsonResponse({"ok": True, "correo": ocultar_correo(correo)})
