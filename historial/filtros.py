"""Filtros del historial (HU10 / RF09). HU11 (exportar CSV) reutiliza filtrar_validaciones()."""
from django.db.models import Prefetch, Q

from configuracion.models import Laboratorio, PeriodoAcademico
from verificacion.models import Validacion, ValidacionDetalle

CAMPOS = ("q", "laboratorio", "periodo", "desde", "hasta", "estado")
ESTADOS = [("", "Todos"), ("conforme", "Cumple"), ("no_conforme", "No cumple"), ("corregidas", "Corregidas")]


def leer_filtros(parametros):
    return {campo: (parametros.get(campo) or "").strip() for campo in CAMPOS}


def filtrar_validaciones(filtros, solo_incidencias=False):
    """Devuelve las validaciones que cumplen TODOS los filtros (CA01)."""
    detalles = ValidacionDetalle.objects.select_related("epp").order_by("epp__nombre")
    validaciones = (
        Validacion.objects.select_related("carnet__estudiante", "laboratorio", "periodo", "usuario_supervisor", "modelo")
        .prefetch_related(Prefetch("detalles", queryset=detalles))
        .order_by("-fecha_hora", "-id_validacion")
    )
    if solo_incidencias:
        validaciones = validaciones.filter(resultado_final=Validacion.NO_CONFORME)  # CA04
    elif filtros["estado"] == "corregidas":
        validaciones = validaciones.filter(corregida=True)
    elif filtros["estado"] in (Validacion.CONFORME, Validacion.NO_CONFORME):
        validaciones = validaciones.filter(resultado_final=filtros["estado"])

    if filtros["laboratorio"].isdigit():
        validaciones = validaciones.filter(laboratorio_id=int(filtros["laboratorio"]))
    if filtros["periodo"].isdigit():
        validaciones = validaciones.filter(periodo_id=int(filtros["periodo"]))
    if filtros["desde"]:
        validaciones = validaciones.filter(fecha_hora__date__gte=filtros["desde"])
    if filtros["hasta"]:
        validaciones = validaciones.filter(fecha_hora__date__lte=filtros["hasta"])
    if filtros["q"]:  # CA02: nombre, apellido o cédula
        q = filtros["q"]
        estudiante = "carnet__estudiante__"
        validaciones = validaciones.filter(
            Q(**{f"{estudiante}nombres__icontains": q}) | Q(**{f"{estudiante}apellidos__icontains": q}) | Q(**{f"{estudiante}cedula__icontains": q})
        )
    return validaciones


def opciones():
    return {
        "laboratorios": Laboratorio.objects.order_by("nombre"),
        "periodos": PeriodoAcademico.objects.order_by("-fecha_inicio"),
        "estados": ESTADOS,
    }


def faltantes(validacion):
    """EPP requeridos que no quedaron detectados (valor final)."""
    return [d.epp.nombre for d in validacion.detalles.all() if d.requerido and not d.detectado_final]
