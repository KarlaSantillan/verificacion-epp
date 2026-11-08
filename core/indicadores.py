"""Cálculo de los indicadores del dashboard (HU14 / RF11).

Todos los indicadores usan el RESULTADO FINAL de la validación (HU14-CA03): si un docente
corrigió una validación (HU09), cuenta lo corregido y no lo que dijo el modelo.

Porcentaje de cumplimiento = validaciones "Cumple" / total de validaciones × 100,
redondeado a 1 decimal (HU14-CA01: debe coincidir con un cálculo manual).
"""
from datetime import date, datetime, timedelta

from django.db.models import Count, Max, Min, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from verificacion.models import Validacion, ValidacionDetalle

DIAS_MAXIMOS_POR_DIA = 14  # hasta 14 días de datos se agrupa por día; si hay más, por semana
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
CUMPLE = Q(resultado_final=Validacion.CONFORME)


def porcentaje(parte, total):
    """Porcentaje con 1 decimal, o None si no hay datos (para no mostrar un 0 % engañoso)."""
    if not total:
        return None
    return round(parte * 100 / total, 1)


def nivel(valor):
    """Color del porcentaje: verde ≥ 90, ámbar 70–89,9 y rojo < 70."""
    if valor is None:
        return "sin-datos"
    if valor >= 90:
        return "alto"
    if valor >= 70:
        return "medio"
    return "bajo"


def validaciones(periodo, laboratorio=None):
    """Validaciones del periodo y, si se eligió, del laboratorio (HU14-CA02)."""
    consulta = Validacion.objects.filter(periodo=periodo)
    if laboratorio is not None:
        consulta = consulta.filter(laboratorio=laboratorio)
    return consulta


def resumen(consulta):
    datos = consulta.aggregate(
        total=Count("pk"),
        conformes=Count("pk", filter=CUMPLE),
        corregidas=Count("pk", filter=Q(corregida=True)),
        estudiantes=Count("carnet__estudiante", distinct=True),
    )
    datos["no_conformes"] = datos["total"] - datos["conformes"]
    datos["porcentaje"] = porcentaje(datos["conformes"], datos["total"])
    datos["nivel"] = nivel(datos["porcentaje"])
    return datos


def epp_faltantes(consulta):
    """EPP requeridos que faltaron en las validaciones "No cumple", del más al menos frecuente.

    Usa detectado_final (lo que quedó tras una posible corrección del docente).
    El porcentaje es sobre el total de incidencias: "faltó en el X % de las incidencias".
    """
    incidencias = consulta.filter(resultado_final=Validacion.NO_CONFORME)
    total_incidencias = incidencias.count()
    filas = (
        ValidacionDetalle.objects.filter(validacion__in=incidencias, requerido=True, detectado_final=False)
        .values("epp__nombre")
        .annotate(veces=Count("pk"))
        .order_by("-veces", "epp__nombre")
    )
    return [
        {"nombre": fila["epp__nombre"], "veces": fila["veces"], "porcentaje": porcentaje(fila["veces"], total_incidencias)}
        for fila in filas
    ]


def por_laboratorio(consulta):
    filas = (
        consulta.values("laboratorio__nombre")
        .annotate(total=Count("pk"), conformes=Count("pk", filter=CUMPLE))
        .order_by("laboratorio__nombre")
    )
    resultado = []
    for fila in filas:
        valor = porcentaje(fila["conformes"], fila["total"])
        resultado.append({
            "nombre": fila["laboratorio__nombre"],
            "total": fila["total"],
            "conformes": fila["conformes"],
            "no_conformes": fila["total"] - fila["conformes"],
            "porcentaje": valor,
            "nivel": nivel(valor),
        })
    return resultado


def agrupacion_automatica(consulta):
    """'dia' si los datos abarcan 14 días o menos; si no, 'semana'."""
    rango = consulta.aggregate(primera=Min("fecha_hora"), ultima=Max("fecha_hora"))
    if rango["primera"] is None:
        return "dia"
    dias = (timezone.localtime(rango["ultima"]).date() - timezone.localtime(rango["primera"]).date()).days
    return "dia" if dias <= DIAS_MAXIMOS_POR_DIA else "semana"


def _como_fecha(valor):
    if isinstance(valor, datetime):
        return timezone.localtime(valor).date() if timezone.is_aware(valor) else valor.date()
    return valor


def etiqueta(fecha, agrupacion):
    texto = f"{fecha.day} {MESES[fecha.month - 1]}"
    return f"Sem. {texto}" if agrupacion == "semana" else texto


def serie(consulta, agrupacion):
    """Datos del gráfico: una barra por día (o por semana, que empieza el lunes).

    Los días sin validaciones no aparecen (no se dibujan barras vacías).
    """
    truncar = TruncWeek("fecha_hora") if agrupacion == "semana" else TruncDate("fecha_hora")
    filas = (
        consulta.annotate(grupo=truncar)
        .values("grupo")
        .annotate(total=Count("pk"), conformes=Count("pk", filter=CUMPLE))
        .order_by("grupo")
    )
    resultado = []
    for fila in filas:
        fecha = _como_fecha(fila["grupo"])
        hasta = fecha + timedelta(days=6) if agrupacion == "semana" else fecha
        resultado.append({
            "fecha": fecha.isoformat(),
            "hasta": hasta.isoformat(),
            "etiqueta": etiqueta(fecha, agrupacion),
            "total": fila["total"],
            "conformes": fila["conformes"],
            "no_conformes": fila["total"] - fila["conformes"],
            "porcentaje": porcentaje(fila["conformes"], fila["total"]),
        })
    return resultado


def mensaje_resumen(puntos, agrupacion):
    """Frase de lectura rápida bajo el gráfico (RNF08)."""
    if not puntos:
        return None, None
    if agrupacion == "semana":
        actual = puntos[-1]
        if len(puntos) == 1:
            return f"La última semana el cumplimiento fue de {_num(actual['porcentaje'])} % con {actual['total']} validaciones.", None
        anterior = puntos[-2]
        diferencia = round(actual["porcentaje"] - anterior["porcentaje"], 1)
        if diferencia == 0:
            return f"La última semana el cumplimiento fue de {_num(actual['porcentaje'])} %, igual que la semana anterior.", None
        verbo = "sube" if diferencia > 0 else "baja"
        icono = "graph-up-arrow" if diferencia > 0 else "graph-down-arrow"
        return (
            f"La última semana el cumplimiento fue de {_num(actual['porcentaje'])} %; "
            f"{verbo} {_num(abs(diferencia))} puntos respecto a la semana anterior.",
            icono,
        )
    total = sum(p["total"] for p in puntos)
    conformes = sum(p["conformes"] for p in puntos)
    peor = min(puntos, key=lambda p: (p["porcentaje"], p["fecha"]))
    return (
        f"El cumplimiento del periodo mostrado es de {_num(porcentaje(conformes, total))} %. "
        f"El día con menor cumplimiento fue el {peor['etiqueta']} ({_num(peor['porcentaje'])} %).",
        None,
    )


def _num(valor):
    """82.5 → '82,5' y 80.0 → '80' (formato de Ecuador)."""
    if valor is None:
        return "—"
    return (f"{valor:.1f}".rstrip("0").rstrip(".")).replace(".", ",")
