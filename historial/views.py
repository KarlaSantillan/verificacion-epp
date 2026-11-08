"""Pantallas Registros e Incidencias (HU10 / RF09) y corrección manual (HU09 / RF08)."""
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from verificacion.correccion import CorreccionNoValida, corregir_detalle, tipo_de_error
from verificacion.models import CorreccionValidacion, Validacion, ValidacionDetalle

from .filtros import faltantes, filtrar_validaciones, leer_filtros, opciones


def _lista(request, modo):
    filtros = leer_filtros(request.GET)
    validaciones = filtrar_validaciones(filtros, solo_incidencias=(modo == "incidencias"))
    pagina = Paginator(validaciones, 20).get_page(request.GET.get("pagina"))
    for validacion in pagina:
        validacion.faltantes = faltantes(validacion)
    contexto = {
        "modo": modo,
        "pagina": pagina,
        "filtros": filtros,
        "hay_filtros": any(filtros.values()),
        "parametros_url": urlencode({k: v for k, v in filtros.items() if v}),
        **opciones(),
    }
    return render(request, "historial/registros.html", contexto)


@login_required
def registros(request):
    return _lista(request, "registros")


@login_required
def incidencias(request):
    return _lista(request, "incidencias")


@login_required
def detalle(request, pk):
    """Detalle de una validación: resultado por EPP, original y final, y correcciones (RF09-CA03)."""
    validacion = get_object_or_404(
        Validacion.objects.select_related("carnet__estudiante", "laboratorio", "periodo", "modelo", "usuario_supervisor"), pk=pk
    )
    detalles = validacion.detalles.select_related("epp").order_by("epp__nombre")
    correcciones = (
        CorreccionValidacion.objects.filter(detalle__validacion=validacion)
        .select_related("usuario", "detalle__epp")
        .order_by("-fecha")
    )
    volver = request.GET.get("volver", "")
    contexto = {
        "validacion": validacion,
        "detalles": detalles,
        "correcciones": correcciones,
        "volver": volver if volver.startswith("/") and not volver.startswith("//") else "",
    }
    return render(request, "historial/detalle.html", contexto)


@login_required
def corregir(request, pk, id_detalle):
    """Corregir la detección de un EPP (HU09)."""
    detalle_epp = get_object_or_404(
        ValidacionDetalle.objects.select_related("validacion", "epp"), pk=id_detalle, validacion_id=pk
    )
    valor_nuevo = not detalle_epp.detectado_final  # se propone el valor contrario al actual
    observacion = ""
    error = None
    if request.method == "POST":
        valor_nuevo = request.POST.get("valor_nuevo") == "1"
        observacion = request.POST.get("observacion", "")
        try:
            corregir_detalle(detalle_epp, usuario=request.user, valor_nuevo=valor_nuevo, observacion=observacion)
        except CorreccionNoValida as excepcion:
            error = str(excepcion)
        else:
            validacion = detalle_epp.validacion
            validacion.refresh_from_db()
            messages.success(request, f"Corrección guardada. Resultado final: {validacion.get_resultado_final_display()}.")
            return redirect("historial:detalle", pk=pk)

    contexto = {
        "detalle": detalle_epp,
        "validacion": detalle_epp.validacion,
        "valor_nuevo": valor_nuevo,
        "observacion": observacion,
        "error": error,
        "tipo": dict(CorreccionValidacion.TIPOS_ERROR)[tipo_de_error(detalle_epp.detectado_final, valor_nuevo)],
    }
    return render(request, "historial/corregir.html", contexto)
