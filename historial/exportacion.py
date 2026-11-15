"""Exportación de registros a CSV (HU11 / RF10).

- Exporta EXACTAMENTE las validaciones de la consulta filtrada (CA01): usa los mismos
  leer_filtros() y filtrar_validaciones() que la pantalla, y todas las páginas, no solo la visible.
- Compatible con Excel en Ecuador (CA02): BOM UTF-8 para las tildes y ";" como separador,
  igual que la descarga de reincidentes (HU16).
- Fecha y hora de Ecuador, estudiante, laboratorio, periodo, resultado del modelo, resultado
  final y el estado de cada EPP (RF10-CA03).
- Datos personales mínimos (RNF06): la cédula va enmascarada y nunca se exporta el contenido
  del QR ni su hash (HU11-CA03).
"""
import csv

from django.http import HttpResponse
from django.utils import timezone

from estudiantes.servicios import ocultar_cedula
from verificacion.sesion_practica import separar

from .filtros import faltantes

COLUMNAS_FIJAS = [
    "id_validacion", "fecha", "hora", "estudiante", "cedula", "carrera", "laboratorio", "periodo", "materia", "practica",
    "resultado_modelo", "resultado_final", "corregida", "epp_faltantes", "supervisor", "modelo_vision",
]
PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def seguro(valor):
    """Evita que Excel interprete un texto como fórmula (inyección de CSV)."""
    texto = "" if valor is None else str(valor)
    return f"'{texto}" if texto.startswith(PELIGROSOS) else texto


def estado_epp(detalle):
    """Estado final del EPP; si el docente lo corrigió, se indica (HU09)."""
    if detalle is None:
        return "—"  # el EPP no se evaluó en esa validación
    texto = "Detectado" if detalle.detectado_final else "No detectado"
    if detalle.detectado_final != detalle.detectado_modelo:
        texto += " (corregido)"
    if not detalle.requerido:
        texto += " · no requerido"
    return texto


def nombre_archivo(prefijo):
    return f"{prefijo}_epp_{timezone.localtime().strftime('%Y%m%d_%H%M')}.csv"


def respuesta_csv(validaciones, prefijo):
    """Arma el archivo CSV con las validaciones recibidas (ya filtradas)."""
    validaciones = list(validaciones)
    # Una columna por cada EPP que aparece en las validaciones exportadas, en orden alfabético.
    nombres_epp = sorted({d.epp.nombre for v in validaciones for d in v.detalles.all()})

    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo(prefijo)}"'
    respuesta.write("﻿")  # BOM: Excel reconoce las tildes
    escritor = csv.writer(respuesta, delimiter=";")
    escritor.writerow(COLUMNAS_FIJAS + [f"epp_{n}" for n in nombres_epp])

    for v in validaciones:
        fecha_hora = timezone.localtime(v.fecha_hora)  # hora de Ecuador (America/Guayaquil)
        estudiante = v.carnet.estudiante
        supervisor = v.usuario_supervisor
        por_epp = {d.epp.nombre: d for d in v.detalles.all()}
        escritor.writerow(
            [
                v.pk,
                fecha_hora.strftime("%d/%m/%Y"),
                fecha_hora.strftime("%H:%M:%S"),
                seguro(estudiante),
                ocultar_cedula(estudiante.cedula) or "",
                seguro(estudiante.carrera),
                seguro(v.laboratorio.nombre),
                seguro(v.periodo.nombre),
                *(seguro(texto) for texto in separar(v.observacion)),
                v.get_resultado_modelo_display(),
                v.get_resultado_final_display(),
                "Sí" if v.corregida else "No",
                ", ".join(faltantes(v)),
                seguro(f"{supervisor.nombres or ''} {supervisor.apellidos or ''}".strip()),
                seguro(v.modelo),
            ]
            + [estado_epp(por_epp.get(n)) for n in nombres_epp]
        )
    return respuesta
