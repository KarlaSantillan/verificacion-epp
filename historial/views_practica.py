"""Editar la materia y la práctica de una validación ya registrada (asesoría del 12/11/2026).

Son datos descriptivos guardados en la observación: no cambian el resultado.
El cambio queda en la auditoría (TK08).
"""
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from verificacion.models import Validacion
from verificacion.sesion_practica import componer


@login_required
@require_POST
def editar_practica(request, pk):
    validacion = get_object_or_404(Validacion, pk=pk)
    validacion.observacion = componer(request.POST.get("materia"), request.POST.get("practica")) or None
    validacion.save(update_fields=["observacion"])
    messages.success(request, "Materia y práctica actualizadas.")
    destino = reverse("historial:detalle", args=[pk])
    volver = request.POST.get("volver", "")
    if volver.startswith("/") and not volver.startswith("//"):
        destino += f"?volver={quote(volver)}"
    return redirect(destino)
