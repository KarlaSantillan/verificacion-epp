"""Revisión de carnés pendientes (HU05 / RF04-CA02, CA03 y CA05).

Un carné queda "Pendiente de revisión" cuando el SGA no respondió al registrarlo.
Desde la lista de pendientes se puede volver a consultar el SGA o completar los
datos a mano después de revisar la página de validación.
"""
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from .models import CarnetEstudiantil, Estudiante
from .servicios import _aplicar_datos_sga, _consultar_sga

CAMPOS_ESTUDIANTE = ("nombres", "apellidos", "carrera", "facultad", "modalidad", "nivel")


def carnets_pendientes():
    return (
        CarnetEstudiantil.objects.select_related("estudiante", "usuario_registro")
        .filter(estado_registro=CarnetEstudiantil.PENDIENTE, activo=True)
        .order_by("fecha_creacion")
    )


def reconsultar_sga(carnet):
    """Vuelve a consultar el SGA. Devuelve 'registrado', 'no_valido' o 'sin_respuesta'."""
    datos = _consultar_sga(carnet.codigo_validacion)
    if datos is None:
        return "sin_respuesta"
    if not datos.valido:
        return "no_valido"
    with transaction.atomic():
        _aplicar_datos_sga(carnet, datos)
    return "registrado"


def _eliminar_si_quedo_vacio(estudiante):
    """Borra el estudiante vacío que se creó con el carné, si ya no tiene carnés."""
    if estudiante.carnets.exists():
        return
    try:
        estudiante.delete()
    except ProtectedError:  # tiene otros registros asociados: se desactiva en lugar de borrarse
        estudiante.activo = False
        estudiante.save(update_fields=["activo"])


@transaction.atomic
def completar_carnet(carnet, datos):
    """Guarda los datos escritos por el docente y marca el carné como registrado.

    Si la cédula ya pertenece a otro estudiante, el carné se asocia a ese
    estudiante y no se crea un duplicado (RF04-CA05). Las validaciones apuntan
    al carné, así que las anteriores muestran el nombre automáticamente (CA03).
    Devuelve True si el carné se asoció a un estudiante existente.
    """
    cedula = (datos.get("cedula") or "").strip() or None
    existente = None
    if cedula:
        existente = Estudiante.objects.filter(cedula=cedula).exclude(pk=carnet.estudiante_id).first()

    if existente:
        vacio = carnet.estudiante
        carnet.estudiante = existente
        estudiante = existente
        # Solo se completan los datos que le falten al estudiante existente.
        for campo in CAMPOS_ESTUDIANTE:
            if datos.get(campo) and not getattr(estudiante, campo):
                setattr(estudiante, campo, datos[campo])
    else:
        vacio = None
        estudiante = carnet.estudiante
        estudiante.cedula = cedula
        for campo in CAMPOS_ESTUDIANTE:
            setattr(estudiante, campo, datos.get(campo) or None)
    estudiante.save()

    if datos.get("fecha_fin_vigencia"):
        carnet.fecha_fin_vigencia = datos["fecha_fin_vigencia"]
    carnet.estado_registro = CarnetEstudiantil.REGISTRADO
    carnet.fecha_revision = timezone.now()
    carnet.save()

    if vacio is not None:
        _eliminar_si_quedo_vacio(vacio)
    return existente is not None
