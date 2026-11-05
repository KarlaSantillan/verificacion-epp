"""Pantallas de administración con el diseño del prototipo (HU12 / HU13).

Reemplazan al panel de Django para el uso diario. Solo el administrador entra
(core.decorators.solo_administrador). Los registros se desactivan, no se eliminan (HU13-CA01).
"""
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from configuracion.models import Epp, Laboratorio, LaboratorioEpp, ModeloVision, Parametro, PeriodoAcademico
from core.decorators import solo_administrador
from estudiantes.models import CarnetEstudiantil, Estudiante
from usuarios.models import Rol, Usuario

from .forms import (
    EppForm,
    EstudianteForm,
    LaboratorioForm,
    ModeloVisionForm,
    ParametroForm,
    PeriodoForm,
    RequisitosForm,
    UsuarioForm,
)


def _formulario(request, form, plantilla, contexto, exito, destino):
    """Patrón común: si el formulario es válido se guarda y se vuelve a la lista."""
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, exito)
        return redirect(destino)
    return render(request, plantilla, {"form": form, **contexto})


# ---------------------------------------------------------------- Laboratorios (HU12)

@solo_administrador
def laboratorios(request):
    obligatorios = LaboratorioEpp.objects.filter(activo=True, obligatorio=True, epp__activo=True).select_related("epp")
    lista = Laboratorio.objects.prefetch_related(Prefetch("requisitos", queryset=obligatorios, to_attr="obligatorios")).order_by("nombre")
    return render(request, "administracion/laboratorios.html", {"laboratorios": lista})


@solo_administrador
def laboratorio_editar(request, pk=None):
    laboratorio = get_object_or_404(Laboratorio, pk=pk) if pk else None
    epps = Epp.objects.filter(activo=True).order_by("nombre")
    existentes = {r.epp_id: r for r in LaboratorioEpp.objects.filter(laboratorio=laboratorio)} if laboratorio else {}

    datos = request.POST if request.method == "POST" else None
    form = LaboratorioForm(datos, instance=laboratorio, prefix="lab")
    requisitos = RequisitosForm(datos, epps=epps, existentes=existentes, prefix="req")

    if request.method == "POST" and form.is_valid() and requisitos.is_valid():
        with transaction.atomic():
            laboratorio = form.save()
            for epp, habilitado, obligatorio, confianza in requisitos.requisitos():
                actual = existentes.get(epp.id_epp)
                if actual is None and not habilitado:
                    continue  # nunca estuvo configurado: no se crea una fila vacía
                actual = actual or LaboratorioEpp(laboratorio=laboratorio, epp=epp)
                actual.activo, actual.obligatorio, actual.confianza_minima = habilitado, obligatorio, confianza
                actual.save()
        if not any(obligatorio for _, _, obligatorio, _ in requisitos.requisitos()):
            messages.warning(request, f"{laboratorio} no tiene EPP obligatorios: no podrá usarse en la verificación.")
        messages.success(request, "Configuración guardada. Aplica a las evaluaciones futuras; los registros anteriores no cambian.")
        return redirect("administracion:laboratorios")

    return render(request, "administracion/laboratorio_form.html", {"form": form, "requisitos": requisitos, "laboratorio": laboratorio})


# ---------------------------------------------------------------- Catálogo EPP

@solo_administrador
def catalogo(request):
    return render(request, "administracion/catalogo.html", {"epps": Epp.objects.order_by("nombre")})


@solo_administrador
def epp_editar(request, pk=None):
    epp = get_object_or_404(Epp, pk=pk) if pk else None
    form = EppForm(request.POST or None, instance=epp)
    return _formulario(request, form, "administracion/epp_form.html", {"epp": epp}, "EPP guardado.", "administracion:catalogo")


# ---------------------------------------------------------------- Estudiantes y carnés

@solo_administrador
def estudiantes(request):
    pestana = "carnes" if request.GET.get("tab") == "carnes" else "estudiantes"
    busqueda = request.GET.get("q", "").strip()
    if pestana == "estudiantes":
        lista = Estudiante.objects.annotate(total_carnes=Count("carnets")).order_by("apellidos", "nombres")
        if busqueda:
            lista = lista.filter(Q(nombres__icontains=busqueda) | Q(apellidos__icontains=busqueda) | Q(cedula__icontains=busqueda))
    else:
        lista = CarnetEstudiantil.objects.select_related("estudiante", "usuario_registro").order_by("-fecha_creacion")
        if busqueda:
            lista = lista.filter(
                Q(codigo_validacion__icontains=busqueda) | Q(estudiante__nombres__icontains=busqueda) | Q(estudiante__apellidos__icontains=busqueda)
            )
    pagina = Paginator(lista, 20).get_page(request.GET.get("pagina"))
    pendientes = CarnetEstudiantil.objects.filter(estado_registro=CarnetEstudiantil.PENDIENTE, activo=True).count()
    return render(
        request, "administracion/estudiantes.html",
        {"pestana": pestana, "pagina": pagina, "busqueda": busqueda, "pendientes": pendientes},
    )


@solo_administrador
def estudiante_editar(request, pk):
    estudiante = get_object_or_404(Estudiante, pk=pk)
    form = EstudianteForm(request.POST or None, instance=estudiante)
    contexto = {"estudiante": estudiante, "carnets": estudiante.carnets.order_by("-fecha_creacion")}
    return _formulario(request, form, "administracion/estudiante_form.html", contexto, "Estudiante actualizado.", "administracion:estudiantes")


# ---------------------------------------------------------------- Usuarios y roles

@solo_administrador
def usuarios(request):
    return render(request, "administracion/usuarios.html", {"usuarios": Usuario.objects.select_related("rol").order_by("apellidos", "nombres")})


@solo_administrador
def usuario_editar(request, pk=None):
    usuario = get_object_or_404(Usuario, pk=pk) if pk else None
    form = UsuarioForm(request.POST or None, instance=usuario)
    if request.method == "POST" and form.is_valid():
        if usuario == request.user and (not form.cleaned_data["activo"] or form.cleaned_data["rol"].nombre != Rol.ADMINISTRADOR):
            form.add_error(None, "No puede desactivarse ni quitarse el rol de administrador a sí mismo.")
        else:
            form.save()
            messages.success(request, "Usuario guardado.")
            return redirect("administracion:usuarios")
    return render(request, "administracion/usuario_form.html", {"form": form, "usuario": usuario})


# ---------------------------------------------------------------- Periodos académicos

@solo_administrador
def periodos(request):
    form = PeriodoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Periodo creado.")
        return redirect("administracion:periodos")
    return render(request, "administracion/periodos.html", {"periodos": PeriodoAcademico.objects.order_by("-fecha_inicio"), "form": form})


@solo_administrador
def periodo_editar(request, pk):
    periodo = get_object_or_404(PeriodoAcademico, pk=pk)
    form = PeriodoForm(request.POST or None, instance=periodo)
    return _formulario(request, form, "administracion/periodo_form.html", {"periodo": periodo}, "Periodo actualizado.", "administracion:periodos")


# ---------------------------------------------------------------- Parámetros generales

@solo_administrador
def parametros(request):
    return render(request, "administracion/parametros.html", {"parametros": Parametro.objects.order_by("clave")})


@solo_administrador
def parametro_editar(request, pk):
    parametro = get_object_or_404(Parametro, pk=pk)
    form = ParametroForm(request.POST or None, instance=parametro)
    return _formulario(request, form, "administracion/parametro_form.html", {"parametro": parametro}, "Parámetro actualizado.", "administracion:parametros")


# ---------------------------------------------------------------- Modelo de visión

def _archivo_modelo(modelo):
    carpeta = Path(getattr(settings, "MODELOS_DIR", Path(settings.BASE_DIR) / "modelos"))
    return carpeta / f"epp_{modelo.version}.pt"


@transaction.atomic
def _activar(modelo):
    """Solo un modelo activo a la vez (HU13-CA03): se desactivan los demás primero."""
    ModeloVision.objects.exclude(pk=modelo.pk).filter(activo=True).update(activo=False)
    modelo.activo = True
    modelo.save(update_fields=["activo"])


@solo_administrador
def modelos(request):
    lista = list(ModeloVision.objects.order_by("-activo", "-fecha_entrenamiento", "-id_modelo"))
    for modelo in lista:
        modelo.archivo = f"modelos/{_archivo_modelo(modelo).name}"
        modelo.archivo_existe = _archivo_modelo(modelo).exists()
    return render(request, "administracion/modelos.html", {"modelos": lista})


@solo_administrador
def modelo_editar(request, pk=None):
    modelo = get_object_or_404(ModeloVision, pk=pk) if pk else None
    form = ModeloVisionForm(request.POST or None, instance=modelo)
    return _formulario(request, form, "administracion/modelo_form.html", {"modelo": modelo}, "Modelo guardado.", "administracion:modelos")


@solo_administrador
@require_POST
def modelo_activar(request, pk):
    modelo = get_object_or_404(ModeloVision, pk=pk)
    if not _archivo_modelo(modelo).exists():
        messages.error(request, f"No se encontró el archivo modelos/{_archivo_modelo(modelo).name}. Cópielo antes de activar el modelo.")
    else:
        _activar(modelo)
        messages.success(request, f"{modelo} es ahora el modelo activo. Las validaciones anteriores conservan su modelo.")
    return redirect("administracion:modelos")


# ---------------------------------------------------------------- Activar / desactivar (HU13-CA01)

DESACTIVABLES = {
    "laboratorio": (Laboratorio, "administracion:laboratorios"),
    "epp": (Epp, "administracion:catalogo"),
    "usuario": (Usuario, "administracion:usuarios"),
    "estudiante": (Estudiante, "administracion:estudiantes"),
    "carnet": (CarnetEstudiantil, "administracion:estudiantes"),
}


@solo_administrador
@require_POST
def cambiar_activo(request, tipo, pk):
    if tipo not in DESACTIVABLES:
        raise Http404
    modelo, destino = DESACTIVABLES[tipo]
    objeto = get_object_or_404(modelo, pk=pk)
    if objeto == request.user:
        messages.error(request, "No puede desactivar su propia cuenta.")
    else:
        objeto.activo = not objeto.activo
        objeto.save(update_fields=["activo"])
        messages.success(request, f"{objeto}: {'activado' if objeto.activo else 'desactivado'}.")
    siguiente = request.POST.get("siguiente", "")
    if siguiente.startswith("/") and not siguiente.startswith("//"):
        return redirect(siguiente)
    return redirect(destino)
