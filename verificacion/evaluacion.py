"""Evaluación del cumplimiento de EPP según el laboratorio (HU07 / RF06).

Esta es la regla oficial del resultado: la pantalla la aplica en vivo para mostrar
el avance, pero el resultado final siempre lo calcula el servidor con esta función
(y HU08 lo guardará con este mismo cálculo).
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from configuracion.models import LaboratorioEpp


class SinRequisitos(Exception):
    """El laboratorio no tiene EPP obligatorios configurados."""


@dataclass
class DetalleEvaluacion:
    id_epp: int
    epp: str
    clase: str
    requerido: bool
    confianza: Decimal | None
    umbral: Decimal
    detectado: bool


@dataclass
class Evaluacion:
    cumple: bool
    detalles: list

    @property
    def faltantes(self):
        return [d.epp for d in self.detalles if d.requerido and not d.detectado]


def _a_decimal(valor):
    """Convierte la confianza recibida a Decimal entre 0 y 1 (None si no es válida)."""
    try:
        numero = Decimal(str(valor)).quantize(Decimal("0.0001"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return numero if Decimal("0") <= numero <= Decimal("1") else None


def evaluar(laboratorio, confianzas):
    """Compara las confianzas detectadas con los requisitos del laboratorio.

    confianzas: {"lab_coat": 0.84, "gloves": 0.80, ...} (clase del modelo → confianza).
    - Un EPP cuenta como detectado si su confianza es IGUAL O MAYOR al umbral (CA01).
    - Los EPP no obligatorios se informan, pero no cambian el resultado (CA04).
    """
    requisitos = (
        LaboratorioEpp.objects.filter(laboratorio=laboratorio, activo=True, epp__activo=True)
        .select_related("epp")
        .order_by("epp__nombre")
    )
    detalles = []
    for requisito in requisitos:
        confianza = _a_decimal(confianzas.get(requisito.epp.clase_modelo)) if confianzas else None
        detalles.append(
            DetalleEvaluacion(
                id_epp=requisito.epp.id_epp,
                epp=requisito.epp.nombre,
                clase=requisito.epp.clase_modelo,
                requerido=requisito.obligatorio,
                confianza=confianza,
                umbral=requisito.confianza_minima,
                detectado=confianza is not None and confianza >= requisito.confianza_minima,
            )
        )
    if not any(d.requerido for d in detalles):
        raise SinRequisitos("El laboratorio no tiene EPP obligatorios configurados.")
    return Evaluacion(cumple=all(d.detectado for d in detalles if d.requerido), detalles=detalles)
