"""Estudiantes reincidentes y llamados de atención (HU15 / RF12 y HU16 / RF13).

Regla (umbral U = parámetro "umbral_incidencias"):
- Una incidencia es una validación con resultado FINAL "No cumple" (las corregidas a "Cumple" no cuentan, RF12-CA02).
- Se cuentan las incidencias del periodo desde el último llamado de atención.
- ≥ U → "Requiere llamado de atención" · U − 1 → "En observación" · con llamados y menos → "Llamado registrado".
- Al cambiar el umbral todo se recalcula al momento, porque nada se guarda: se calcula al consultar (RF12-CA05).
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from configuracion.models import Parametro, PeriodoAcademico
from estudiantes.models import Estudiante
from verificacion.models import Validacion

from .models import LlamadoAtencion

REQUIERE = "Requiere llamado de atención"
OBSERVACION = "En observación"
REGISTRADO = "Llamado registrado"


class LlamadoNoValido(Exception):
    pass


def umbral():
    try:
        return max(1, int(Parametro.obtener("umbral_incidencias", "3")))
    except (TypeError, ValueError):
        return 3


def periodo_de_trabajo(id_periodo=None):
    """El periodo filtrado; si no hay filtro, el vigente; si no hay vigente, el más reciente."""
    if id_periodo:
        return PeriodoAcademico.objects.filter(pk=id_periodo).first()
    hoy = timezone.localdate()
    vigente = PeriodoAcademico.objects.filter(fecha_inicio__lte=hoy, fecha_fin__gte=hoy).order_by("-fecha_inicio").first()
    return vigente or PeriodoAcademico.objects.order_by("-fecha_inicio").first()


@dataclass
class Reincidente:
    estudiante: Estudiante
    total: int  # incidencias del periodo
    desde_ultimo_llamado: int
    epp_mas_faltante: str | None
    ultima_incidencia: datetime
    estado: str
    ultimo_llamado: LlamadoAtencion | None = None
    incidencias: list = field(default_factory=list)
    epp_faltantes: list = field(default_factory=list)  # [(nombre, veces)] de mayor a menor

    @property
    def resumen_faltantes(self):
        """Todos los EPP que faltaron y cuántas veces: «Mascarilla (12), Bata (11)»."""
        return ", ".join(f"{nombre} ({veces})" for nombre, veces in self.epp_faltantes)

    @property
    def requiere_llamado(self):
        return self.estado == REQUIERE


def _estado(desde, limite, tiene_llamados):
    if desde >= limite:
        return REQUIERE
    if limite >= 2 and desde == limite - 1:
        return OBSERVACION
    return REGISTRADO if tiene_llamados else None


def reincidentes(periodo, laboratorio=None):
    """Lista de estudiantes con estado de reincidencia en el periodo (y laboratorio, si se indica)."""
    if periodo is None:
        return []
    limite = umbral()
    incidencias = (
        Validacion.objects.filter(periodo=periodo, resultado_final=Validacion.NO_CONFORME)
        .select_related("carnet__estudiante", "laboratorio")
        .prefetch_related("detalles__epp")
        .order_by("fecha_hora")
    )
    if laboratorio is not None:
        incidencias = incidencias.filter(laboratorio=laboratorio)

    por_estudiante = {}
    for validacion in incidencias:
        por_estudiante.setdefault(validacion.carnet.estudiante_id, []).append(validacion)

    llamados = {}
    for llamado in LlamadoAtencion.objects.filter(periodo=periodo, estudiante_id__in=por_estudiante).select_related("usuario").order_by("fecha_hora"):
        llamados.setdefault(llamado.estudiante_id, []).append(llamado)

    resultado = []
    for id_estudiante, lista in por_estudiante.items():
        del_estudiante = llamados.get(id_estudiante, [])
        ultimo = del_estudiante[-1] if del_estudiante else None
        desde = len([v for v in lista if ultimo is None or v.fecha_hora > ultimo.fecha_hora])
        estado = _estado(desde, limite, bool(del_estudiante))
        if estado is None:
            continue
        faltantes = Counter(d.epp.nombre for v in lista for d in v.detalles.all() if d.requerido and not d.detectado_final)
        resultado.append(
            Reincidente(
                estudiante=lista[0].carnet.estudiante,
                total=len(lista),
                desde_ultimo_llamado=desde,
                epp_mas_faltante=faltantes.most_common(1)[0][0] if faltantes else None,
                ultima_incidencia=lista[-1].fecha_hora,
                estado=estado,
                ultimo_llamado=ultimo,
                incidencias=list(reversed(lista)),
                epp_faltantes=faltantes.most_common(),
            )
        )
    orden = {REQUIERE: 0, OBSERVACION: 1, REGISTRADO: 2}
    return sorted(resultado, key=lambda r: (orden[r.estado], -r.desde_ultimo_llamado, -r.total))


def pendientes_de_llamado():
    """Para la campana de notificaciones y el aviso del inicio (RF12-CA01)."""
    periodo = periodo_de_trabajo()
    lista = [r for r in reincidentes(periodo) if r.requiere_llamado]
    return periodo, sorted(lista, key=lambda r: r.ultima_incidencia, reverse=True)


def situacion_estudiante(estudiante, periodo=None):
    """Reincidencia de un estudiante para el aviso en la verificación (RF12-CA04). None si no es reincidente."""
    periodo = periodo or periodo_de_trabajo()
    for r in reincidentes(periodo):
        if r.estudiante.pk == estudiante.pk and r.estado in (REQUIERE, OBSERVACION):
            return r
    return None


@transaction.atomic
def registrar_llamado(*, estudiante, periodo, usuario, observacion):
    """Guarda el llamado de atención (RF13-CA01). Exige observación (CA02) y que el estudiante lo requiera."""
    observacion = (observacion or "").strip()
    if not observacion:
        raise LlamadoNoValido("La observación es obligatoria: describa el llamado de atención realizado.")
    situacion = next((r for r in reincidentes(periodo) if r.estudiante.pk == estudiante.pk), None)
    if situacion is None or not situacion.requiere_llamado:
        raise LlamadoNoValido("Este estudiante no requiere un llamado de atención en este periodo.")
    return LlamadoAtencion.objects.create(
        estudiante=estudiante,
        periodo=periodo,
        usuario=usuario,
        cantidad_incidencias=situacion.desde_ultimo_llamado,
        observacion=observacion,
    )
