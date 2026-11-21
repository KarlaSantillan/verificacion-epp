"""Resumen de la clase al pulsar «Nueva práctica» (cambio sugerido en la tutoría).

No modifica la base de datos: usa las validaciones ya guardadas del docente con la misma materia y
práctica (columna observacion) desde que empezó esa práctica (hora anotada en la sesión del navegador).
Cada estudiante se cuenta una sola vez, con el resultado de su última verificación.
"""
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Validacion
from .sesion_practica import componer, separar

# Dos grupos de verificaciones con la misma materia y práctica, del mismo docente y día, se consideran
# clases distintas si entre una y otra pasan más de 2 horas sin verificaciones.
PAUSA_ENTRE_CLASES = timedelta(hours=2)


@dataclass
class EstudianteResumen:
    nombre: str
    intentos: int
    cumple: bool
    faltantes: list
    corrigio: bool  # tuvo «No cumple» y luego «Cumple» en la misma práctica


@dataclass
class ResumenPractica:
    usuario_id: int
    materia: str
    practica: str
    docente: str
    laboratorios: list
    inicio: datetime | None
    fin: datetime | None
    intentos: int = 0
    estudiantes: list = field(default_factory=list)
    epp_faltantes: list = field(default_factory=list)  # [(nombre, veces)] de mayor a menor

    @property
    def total(self):
        return len(self.estudiantes)

    @property
    def cumplieron(self):
        return sum(1 for e in self.estudiantes if e.cumple)

    @property
    def no_cumplieron(self):
        return [e for e in self.estudiantes if not e.cumple]

    @property
    def corrigieron(self):
        return sum(1 for e in self.estudiantes if e.corrigio)

    @property
    def porcentaje(self):
        return round(100 * self.cumplieron / self.total) if self.total else 0

    @property
    def resumen_faltantes(self):
        return ", ".join(f"{nombre} ({veces})" for nombre, veces in self.epp_faltantes)


def _faltantes(validacion):
    return [d.epp.nombre for d in validacion.detalles.all() if d.requerido and not d.detectado_final]


def inicio_de_practica(datos_sesion):
    """Hora en que empezó la práctica según la sesión; nunca antes del inicio del día de hoy."""
    hoy = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    try:
        inicio = datetime.fromisoformat((datos_sesion or {}).get("inicio", ""))
    except (TypeError, ValueError):
        return hoy
    if timezone.is_naive(inicio):
        inicio = timezone.make_aware(inicio)
    return max(inicio, hoy)


def _consulta():
    return (
        Validacion.objects.select_related("carnet__estudiante", "laboratorio", "usuario_supervisor")
        .prefetch_related("detalles__epp")
        .order_by("fecha_hora", "id_validacion")
    )


def calcular(usuario, materia, practica, desde, hasta=None):
    """Resumen de la práctica de un docente (con esa materia y práctica) entre desde y hasta."""
    observacion = componer(materia, practica)
    validaciones = _consulta().filter(usuario_supervisor=usuario, fecha_hora__gte=desde).filter(
        Q(observacion=observacion) if observacion else (Q(observacion__isnull=True) | Q(observacion=""))
    )
    if hasta is not None:
        validaciones = validaciones.filter(fecha_hora__lte=hasta)
    return armar(list(validaciones), usuario, materia, practica)


def armar(validaciones, usuario, materia, practica):
    por_estudiante = OrderedDict()
    conteo = Counter()
    laboratorios = []
    for v in validaciones:
        por_estudiante.setdefault(v.carnet.estudiante_id, []).append(v)
        if v.resultado_final == Validacion.NO_CONFORME:
            conteo.update(_faltantes(v))
        if v.laboratorio.nombre not in laboratorios:
            laboratorios.append(v.laboratorio.nombre)

    estudiantes = []
    for lista in por_estudiante.values():
        ultima = lista[-1]
        cumple = ultima.resultado_final == Validacion.CONFORME
        estudiantes.append(EstudianteResumen(
            nombre=str(ultima.carnet.estudiante),
            intentos=len(lista),
            cumple=cumple,
            faltantes=[] if cumple else _faltantes(ultima),
            corrigio=cumple and any(v.resultado_final == Validacion.NO_CONFORME for v in lista[:-1]),
        ))
    todas = validaciones
    nombre_docente = f"{usuario.nombres or ''} {usuario.apellidos or ''}".strip() or usuario.correo
    return ResumenPractica(
        usuario_id=usuario.pk,
        materia=materia, practica=practica, docente=nombre_docente, laboratorios=laboratorios,
        inicio=todas[0].fecha_hora if todas else None, fin=todas[-1].fecha_hora if todas else None,
        intentos=len(todas), estudiantes=estudiantes, epp_faltantes=conteo.most_common(),
    )


def practicas(desde, hasta, usuario=None, materia=""):
    """Prácticas anteriores armadas a partir de las validaciones guardadas (sin tabla de sesiones).

    Se agrupan por docente, materia y práctica, día y pausas de más de 2 horas. Devuelve los resúmenes
    de la más reciente a la más antigua.
    """
    validaciones = _consulta().filter(fecha_hora__date__gte=desde, fecha_hora__date__lte=hasta)
    if usuario is not None:
        validaciones = validaciones.filter(usuario_supervisor=usuario)
    if materia:
        validaciones = validaciones.filter(observacion__icontains=materia)
    grupos, actual, clave_actual, ultima = [], [], None, None
    ordenadas = sorted(validaciones, key=lambda v: (v.usuario_supervisor_id, v.observacion or "", v.fecha_hora))
    for v in ordenadas:
        clave = (v.usuario_supervisor_id, v.observacion or "", timezone.localdate(v.fecha_hora))
        if clave != clave_actual or (ultima and v.fecha_hora - ultima > PAUSA_ENTRE_CLASES):
            if actual:
                grupos.append(actual)
            actual, clave_actual = [], clave
        actual.append(v)
        ultima = v.fecha_hora
    if actual:
        grupos.append(actual)
    resumenes = []
    for grupo in grupos:
        materia_g, practica_g = separar(grupo[0].observacion)
        resumenes.append(armar(grupo, grupo[0].usuario_supervisor, materia_g, practica_g))
    return sorted(resumenes, key=lambda r: r.inicio, reverse=True)
