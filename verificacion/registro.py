"""Registro de la validación en la base de datos (HU08 / RF07).

Guarda la validación con el carné, el docente supervisor, el laboratorio, el periodo
vigente, el modelo activo y el detalle de cada EPP con su confianza y el umbral usado.
"""
from django.db import transaction
from django.utils import timezone

from configuracion.models import ModeloVision, PeriodoAcademico

from .models import Validacion, ValidacionDetalle


class RegistroNoPermitido(Exception):
    """Falta algo para poder registrar (periodo vigente, modelo activo...)."""


def periodo_vigente(fecha=None):
    hoy = fecha or timezone.localdate()
    return PeriodoAcademico.objects.filter(fecha_inicio__lte=hoy, fecha_fin__gte=hoy).order_by("-fecha_inicio").first()


def registrar_validacion(*, usuario, carnet, laboratorio, evaluacion):
    """Crea la validación y su detalle en una sola transacción (todo o nada)."""
    periodo = periodo_vigente()
    if periodo is None:
        raise RegistroNoPermitido("No hay un periodo académico vigente. El administrador debe registrarlo en Periodos académicos.")
    modelo = ModeloVision.objects.filter(activo=True).first()
    if modelo is None:
        raise RegistroNoPermitido("No hay un modelo de visión activo.")

    resultado = Validacion.CONFORME if evaluacion.cumple else Validacion.NO_CONFORME
    with transaction.atomic():
        validacion = Validacion.objects.create(
            usuario_supervisor=usuario,  # CA05: el docente de la sesión
            periodo=periodo,
            modelo=modelo,
            carnet=carnet,
            laboratorio=laboratorio,
            resultado_modelo=resultado,
            resultado_final=resultado,  # cambia solo con una corrección manual (HU09)
        )
        ValidacionDetalle.objects.bulk_create(
            ValidacionDetalle(
                validacion=validacion,
                epp_id=detalle.id_epp,
                requerido=detalle.requerido,
                detectado_modelo=detalle.detectado,
                detectado_final=detalle.detectado,
                confianza=detalle.confianza,
                umbral_usado=detalle.umbral,
            )
            for detalle in evaluacion.detalles
        )
    return validacion
