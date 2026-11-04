"""Identificación del estudiante mediante el QR del carné (HU02) y registro de carnés nuevos (HU04).

El QR del carné digital de la UNEMI contiene una dirección como:
    https://sga.unemi.edu.ec/p_valida_carnet/digital?code=2744921411013
Solo se extrae el código; los datos personales NO se obtienen del QR ni del SGA.
"""
import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from configuracion.models import Parametro

from .models import CarnetEstudiantil, Estudiante

PREFIJO_POR_DEFECTO = "https://sga.unemi.edu.ec/p_valida_carnet/"


class QRNoValido(Exception):
    """El contenido leído no corresponde a un carné de la UNEMI."""


def extraer_codigo(texto_qr):
    """Valida el prefijo del QR y devuelve el código de validación (RF02-CA02)."""
    texto = (texto_qr or "").strip()
    prefijo = Parametro.obtener("prefijo_qr_valido", PREFIJO_POR_DEFECTO)
    if not texto.startswith(prefijo):
        raise QRNoValido("El código QR no corresponde a un carné de la UNEMI.")
    codigo = parse_qs(urlparse(texto).query).get("code", [""])[0].strip()
    return validar_codigo(codigo)


def validar_codigo(codigo):
    """Valida el formato del código de validación (también se usará en HU03, ingreso manual)."""
    codigo = (codigo or "").strip()
    if not codigo or not codigo.isalnum() or len(codigo) > 50:
        raise QRNoValido("El código de validación del carné no es válido.")
    return codigo


def calcular_hash(codigo):
    """HMAC-SHA256 del código con una clave secreta del .env (RF02-CA05, RNF06)."""
    clave = getattr(settings, "QR_HASH_KEY", None)
    if not clave:
        raise RuntimeError("Falta la variable QR_HASH_KEY en el archivo .env")
    return hmac.new(clave.encode(), codigo.encode(), hashlib.sha256).hexdigest()


@dataclass
class ResultadoIdentificacion:
    estado: str  # "registrado", "nuevo", "pendiente", "inactivo" o "vencido"
    carnet: CarnetEstudiantil
    mensaje: str

    @property
    def permite_verificar(self):
        return self.estado in ("registrado", "nuevo", "pendiente")


def identificar_por_codigo(codigo, usuario):
    """Busca el carné por su hash; si no existe, lo crea como pendiente (HU04)."""
    qr_hash = calcular_hash(codigo)
    with transaction.atomic():
        carnet = CarnetEstudiantil.objects.select_related("estudiante").filter(qr_hash=qr_hash).first()
        if carnet is None:
            estudiante = Estudiante.objects.create()
            carnet = CarnetEstudiantil.objects.create(
                usuario_registro=usuario,
                estudiante=estudiante,
                qr_hash=qr_hash,
                codigo_validacion=codigo,
                estado_registro=CarnetEstudiantil.PENDIENTE,
            )
            return ResultadoIdentificacion(
                "nuevo", carnet, "Carné nuevo registrado como pendiente de revisión. Puede continuar con la verificación."
            )

    if not carnet.activo or not carnet.estudiante.activo:
        return ResultadoIdentificacion("inactivo", carnet, "El carné está inactivo. No se puede iniciar la verificación.")
    if carnet.fecha_fin_vigencia and carnet.fecha_fin_vigencia < timezone.localdate():
        return ResultadoIdentificacion("vencido", carnet, "La vigencia del carné terminó. No se puede iniciar la verificación.")
    if carnet.estado_registro == CarnetEstudiantil.PENDIENTE:
        return ResultadoIdentificacion(
            "pendiente", carnet, "Carné pendiente de revisión. Complete los datos del estudiante después de la práctica."
        )
    return ResultadoIdentificacion("registrado", carnet, "Estudiante identificado.")


def identificar_por_qr(texto_qr, usuario):
    return identificar_por_codigo(extraer_codigo(texto_qr), usuario)


def ocultar_cedula(cedula):
    """Muestra solo los dos primeros y dos últimos dígitos (RNF06)."""
    if not cedula or len(cedula) < 5:
        return cedula
    return f"{cedula[:2]}{'•' * (len(cedula) - 4)}{cedula[-2:]}"
