from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CompletarCarnetForm
from .models import CarnetEstudiantil
from .revision import carnets_pendientes, completar_carnet, reconsultar_sga
from .sga import url_validacion


def _pendiente(id_carnet):
    return get_object_or_404(
        CarnetEstudiantil.objects.select_related("estudiante"),
        pk=id_carnet, estado_registro=CarnetEstudiantil.PENDIENTE, activo=True,
    )


@login_required
def pendientes(request):
    """Lista de carnés pendientes de revisión (HU05-CA01)."""
    carnets = list(carnets_pendientes())
    for carnet in carnets:
        carnet.url_sga = url_validacion(carnet.codigo_validacion) if carnet.codigo_validacion else None
    return render(request, "estudiantes/pendientes.html", {"carnets": carnets})


@login_required
@require_POST
def reconsultar(request, id_carnet):
    carnet = _pendiente(id_carnet)
    resultado = reconsultar_sga(carnet)
    if resultado == "registrado":
        messages.success(request, f"Carné {carnet.codigo_validacion} registrado con los datos del SGA: {carnet.estudiante}.")
    elif resultado == "no_valido":
        messages.error(request, f"El SGA indica que el carné {carnet.codigo_validacion} no es válido. Sigue pendiente.")
    else:
        messages.warning(request, "El SGA no respondió. Intente de nuevo más tarde o complete los datos a mano.")
    return redirect("estudiantes:pendientes")


@login_required
def completar(request, id_carnet):
    """Formulario para completar los datos a mano (HU05-CA02 y CA03)."""
    carnet = _pendiente(id_carnet)
    estudiante = carnet.estudiante
    datos_actuales = {
        "nombres": estudiante.nombres, "apellidos": estudiante.apellidos, "cedula": estudiante.cedula,
        "carrera": estudiante.carrera, "facultad": estudiante.facultad, "modalidad": estudiante.modalidad,
        "nivel": estudiante.nivel, "fecha_fin_vigencia": carnet.fecha_fin_vigencia,
    }
    form = CompletarCarnetForm(request.POST or None, initial=datos_actuales)
    if request.method == "POST" and form.is_valid():
        asociado = completar_carnet(carnet, form.cleaned_data)
        if asociado:
            messages.success(request, f"La cédula ya estaba registrada: el carné se asoció a {carnet.estudiante}.")
        else:
            messages.success(request, f"Carné {carnet.codigo_validacion} registrado a nombre de {carnet.estudiante}.")
        return redirect("estudiantes:pendientes")
    contexto = {
        "carnet": carnet,
        "form": form,
        "url_sga": url_validacion(carnet.codigo_validacion) if carnet.codigo_validacion else None,
    }
    return render(request, "estudiantes/completar.html", contexto)
