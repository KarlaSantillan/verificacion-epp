"""Corrección manual de resultados (HU09 / RF08).

El docente cambia el valor final de un EPP cuando el modelo se equivocó.
- Se guarda la corrección con el tipo de error, el valor anterior y el nuevo, la observación,
  el usuario y la fecha (CA01).
- El resultado final se recalcula y la validación queda marcada como corregida (CA02).
- El resultado original del modelo NO se modifica (CA03).
- La corrección y el cambio de la validación quedan en la auditoría automáticamente (TK08 / CA05).
"""
from django.db import transaction

from .models import CorreccionValidacion, Validacion


class CorreccionNoValida(Exception):
    pass


def tipo_de_error(valor_anterior, valor_nuevo):
    """Detectado → no detectado: falso positivo. No detectado → detectado: falso negativo."""
    return CorreccionValidacion.FALSO_POSITIVO if valor_anterior and not valor_nuevo else CorreccionValidacion.FALSO_NEGATIVO


def recalcular(validacion):
    """Cumple si todos los EPP requeridos quedaron detectados en su valor final."""
    requeridos = validacion.detalles.filter(requerido=True)
    cumple = requeridos.exists() and not requeridos.filter(detectado_final=False).exists()
    return Validacion.CONFORME if cumple else Validacion.NO_CONFORME


@transaction.atomic
def corregir_detalle(detalle, *, usuario, valor_nuevo, observacion):
    observacion = (observacion or "").strip()
    if not observacion:
        raise CorreccionNoValida("La observación es obligatoria: explique el motivo de la corrección.")  # CA04
    if bool(valor_nuevo) == detalle.detectado_final:
        raise CorreccionNoValida("El valor nuevo es igual al actual: no hay nada que corregir.")

    correccion = CorreccionValidacion.objects.create(
        usuario=usuario,
        detalle=detalle,
        tipo_error=tipo_de_error(detalle.detectado_final, valor_nuevo),
        valor_anterior=detalle.detectado_final,
        valor_nuevo=bool(valor_nuevo),
        observacion=observacion,
    )
    detalle.detectado_final = bool(valor_nuevo)  # detectado_modelo no se toca (CA03)
    detalle.save(update_fields=["detectado_final"])

    validacion = detalle.validacion
    validacion.resultado_final = recalcular(validacion)  # resultado_modelo no se toca (CA03)
    validacion.corregida = True
    validacion.save(update_fields=["resultado_final", "corregida"])
    return correccion
