"""Pantallas Registros e Incidencias (HU10 / RF09), corrección manual (HU09 / RF08)
y estudiantes reincidentes con llamado de atención (HU15 / RF12, HU16 / RF13)."""
import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from configuracion.models import Laboratorio
from estudiantes.models import Estudiante
from estudiantes.servicios import ocultar_cedula
from seguimiento.models import LlamadoAtencion
from seguimiento.reincidencia import (
    OBSERVACION, REGISTRADO, REQUIERE, LlamadoNoValido, periodo_de_trabajo, registrar_llamado, reincidentes, umbral,
)
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
    if request.GET.get("tab") == "reincidentes":
        return _reincidentes(request)
    return _lista(request, "incidencias")


# ---------------------------------------------------------------- Reincidentes (HU15 / HU16)

def _filtros_reincidentes(request):
    filtros = leer_filtros(request.GET)
    periodo = periodo_de_trabajo(int(filtros["periodo"]) if filtros["periodo"].isdigit() else None)
    laboratorio = Laboratorio.objects.filter(pk=filtros["laboratorio"]).first() if filtros["laboratorio"].isdigit() else None
    lista = reincidentes(periodo, laboratorio)
    if filtros["q"]:
        q = filtros["q"].lower()
        lista = [r for r in lista if q in f"{r.estudiante} {r.estudiante.cedula or ''}".lower()]
    return filtros, periodo, laboratorio, lista


def _reincidentes(request):
    filtros, periodo, laboratorio, lista = _filtros_reincidentes(request)
    contexto = {
        "modo": "incidencias",
        "pestana": "reincidentes",
        "filtros": filtros,
        "periodo_actual": periodo,
        "reincidentes": lista,
        "umbral": umbral(),
        "totales": {
            "requiere": sum(r.estado == REQUIERE for r in lista),
            "observacion": sum(r.estado == OBSERVACION for r in lista),
            "registrado": sum(r.estado == REGISTRADO for r in lista),
        },
        "parametros_url": urlencode({k: v for k, v in filtros.items() if v and k != "estado"}),
        **opciones(),
    }
    return render(request, "historial/registros.html", contexto)


@login_required
def reincidentes_csv(request):
    """Descarga de reincidentes del periodo y laboratorio filtrados (RF13-CA04). Compatible con Excel."""
    filtros, periodo, laboratorio, lista = _filtros_reincidentes(request)
    nombre = f"reincidentes_epp_{(periodo.nombre if periodo else 'sin_periodo').replace(' ', '')}.csv"
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    respuesta.write("\ufeff")  # BOM: Excel reconoce las tildes
    escritor = csv.writer(respuesta, delimiter=";")
    escritor.writerow([
        "estudiante", "cedula", "carrera", "periodo", "laboratorio", "incidencias_periodo", "incidencias_desde_ultimo_llamado",
        "epp_mas_faltante", "ultima_incidencia", "estado", "fecha_ultimo_llamado", "observacion_ultimo_llamado",
    ])
    zona = timezone.get_current_timezone()
    for r in lista:
        escritor.writerow([
            str(r.estudiante), ocultar_cedula(r.estudiante.cedula) or "", r.estudiante.carrera or "",
            periodo.nombre if periodo else "", laboratorio.nombre if laboratorio else "Todos",
            r.total, r.desde_ultimo_llamado, r.epp_mas_faltante or "",
            r.ultima_incidencia.astimezone(zona).strftime("%d/%m/%Y %H:%M"), r.estado,
            r.ultimo_llamado.fecha_hora.astimezone(zona).strftime("%d/%m/%Y %H:%M") if r.ultimo_llamado else "",
            r.ultimo_llamado.observacion if r.ultimo_llamado else "",
        ])
    return respuesta


def _situacion(request, id_estudiante):
    estudiante = get_object_or_404(Estudiante, pk=id_estudiante)
    periodo = periodo_de_trabajo(int(request.GET["periodo"]) if request.GET.get("periodo", "").isdigit() else None)
    if periodo is None:
        raise Http404
    situacion = next((r for r in reincidentes(periodo) if r.estudiante.pk == estudiante.pk), None)
    return estudiante, periodo, situacion


@login_required
def historial_estudiante(request, id_estudiante):
    """Incidencias del periodo y llamados anteriores de un estudiante."""
    estudiante, periodo, situacion = _situacion(request, id_estudiante)
    llamados = LlamadoAtencion.objects.filter(estudiante=estudiante, periodo=periodo).select_related("usuario").order_by("-fecha_hora")
    incidencias_lista = situacion.incidencias if situacion else []
    for validacion in incidencias_lista:
        validacion.faltantes = faltantes(validacion)
    contexto = {"estudiante": estudiante, "periodo": periodo, "situacion": situacion, "incidencias": incidencias_lista, "llamados": llamados,
                "cedula": ocultar_cedula(estudiante.cedula)}
    return render(request, "historial/reincidente.html", contexto)


@login_required
def llamado(request, id_estudiante):
    """Registrar el llamado de atención (HU16 / RF13-CA01, CA02)."""
    estudiante, periodo, situacion = _situacion(request, id_estudiante)
    observacion, error = "", None
    if request.method == "POST":
        observacion = request.POST.get("observacion", "")
        try:
            registrar_llamado(estudiante=estudiante, periodo=periodo, usuario=request.user, observacion=observacion)
        except LlamadoNoValido as excepcion:
            error = str(excepcion)
        else:
            messages.success(request, f"Llamado de atención registrado para {estudiante}.")
            return redirect(f"{reverse('historial:incidencias')}?tab=reincidentes&periodo={periodo.pk}")
    contexto = {"estudiante": estudiante, "periodo": periodo, "situacion": situacion, "observacion": observacion, "error": error}
    return render(request, "historial/llamado.html", contexto)


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
