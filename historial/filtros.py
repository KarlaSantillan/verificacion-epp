"""Filtros del historial (HU10 / RF09). HU11 (exportar CSV) reutiliza filtrar_validaciones()."""
import re

from django.db.models import Prefetch, Q

from configuracion.models import Laboratorio, PeriodoAcademico
from verificacion.models import Validacion, ValidacionDetalle
from verificacion.sesion_practica import separar

CAMPOS = ("q", "laboratorio", "periodo", "desde", "hasta", "estado", "materia", "practica")
ESTADOS = [("", "Todos"), ("conforme", "Cumple"), ("no_conforme", "No cumple"), ("corregidas", "Corregidas")]


def leer_filtros(parametros, usuario=None):
    filtros = {campo: (parametros.get(campo) or "").strip() for campo in CAMPOS}
    # "Solo mis verificaciones": activado por defecto para el docente y desactivado para el administrador.
    # La reincidencia y la campana siempre cuentan las validaciones de todos los docentes.
    mios = (parametros.get("mios") or "").strip()
    if mios not in ("0", "1"):
        mios = "1" if usuario is not None and not getattr(usuario, "es_administrador", False) else "0"
    filtros["mios"] = mios
    return filtros


def filtrar_validaciones(filtros, solo_incidencias=False, usuario=None):
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

    if filtros.get("mios") == "1" and usuario is not None:
        validaciones = validaciones.filter(usuario_supervisor=usuario)
    if filtros["laboratorio"].isdigit():
        validaciones = validaciones.filter(laboratorio_id=int(filtros["laboratorio"]))
    if filtros["periodo"].isdigit():
        validaciones = validaciones.filter(periodo_id=int(filtros["periodo"]))
    if filtros["desde"]:
        validaciones = validaciones.filter(fecha_hora__date__gte=filtros["desde"])
    if filtros["hasta"]:
        validaciones = validaciones.filter(fecha_hora__date__lte=filtros["hasta"])
    # Materia y práctica (asesoría 12/11/2026): se guardan en la observación como
    # "Materia: ... | Práctica: ..."; coincidencia parcial y sin distinguir mayúsculas.
    if filtros["materia"]:
        validaciones = validaciones.filter(observacion__iregex=r"^Materia: [^|]*" + re.escape(filtros["materia"]))
    if filtros["practica"]:
        validaciones = validaciones.filter(observacion__iregex=r"\| Práctica: .*" + re.escape(filtros["practica"]))
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
        "materias": _valores_usados(0),  # sugerencias para los filtros
        "practicas": _valores_usados(1),
    }


def _valores_usados(posicion):
    textos = Validacion.objects.filter(observacion__startswith="Materia: ").values_list("observacion", flat=True).distinct()[:300]
    return sorted({valor for texto in textos if (valor := separar(texto)[posicion])})[:100]


def faltantes(validacion):
    """EPP requeridos que no quedaron detectados (valor final)."""
    return [d.epp.nombre for d in validacion.detalles.all() if d.requerido and not d.detectado_final]
