"""Identificación del estudiante mediante el QR del carné (HU02) y registro de carnés nuevos (HU04).

El QR del carné digital de la UNEMI contiene una dirección como:
    https://sga.unemi.edu.ec/p_valida_carnet/digital?code=1234567890123
Del QR solo se extrae el código. Con ese código se consulta la página pública de
validación del SGA (módulo sga.py) para completar los datos del estudiante.
"""
import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from configuracion.models import Parametro

from . import sga
from .models import CarnetEstudiantil, Estudiante
from .sga import PREFIJO_POR_DEFECTO  # noqa: F401  (se mantiene para el resto del código)


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
    estado: str  # "registrado", "nuevo", "pendiente", "inactivo", "vencido" o "no_valido_sga"
    carnet: CarnetEstudiantil | None
    mensaje: str

    @property
    def permite_verificar(self):
        return self.estado in ("registrado", "nuevo", "pendiente")


def _consultar_sga(codigo):
    """Consulta el SGA si está activado en settings (en las pruebas se desactiva)."""
    if not getattr(settings, "SGA_CONSULTA_ACTIVA", True):
        return None
    return sga.consultar(codigo)


def _aplicar_datos_sga(carnet, datos):
    """Copia los datos del SGA al estudiante y marca el carné como registrado."""
    estudiante = carnet.estudiante
    for campo in ("nombres", "apellidos", "carrera", "facultad", "modalidad", "nivel"):
        valor = getattr(datos, campo)
        if valor:
            setattr(estudiante, campo, valor[:120])
    estudiante.save()
    carnet.fecha_inicio_vigencia = datos.inicio_vigencia or carnet.fecha_inicio_vigencia
    carnet.fecha_fin_vigencia = datos.fin_vigencia or carnet.fecha_fin_vigencia
    carnet.estado_registro = CarnetEstudiantil.REGISTRADO
    carnet.fecha_revision = timezone.now()
    carnet.save()


def _estado_carnet(carnet):
    if not carnet.activo or not carnet.estudiante.activo:
        return ResultadoIdentificacion("inactivo", carnet, "El carné está inactivo. No se puede iniciar la verificación.")
    if carnet.fecha_fin_vigencia and carnet.fecha_fin_vigencia < timezone.localdate():
        return ResultadoIdentificacion("vencido", carnet, "La vigencia del carné terminó. No se puede iniciar la verificación.")
    if carnet.estado_registro == CarnetEstudiantil.PENDIENTE:
        return ResultadoIdentificacion(
            "pendiente", carnet, "Carné pendiente de revisión: no se pudieron obtener sus datos del SGA. Puede continuar con la verificación."
        )
    return ResultadoIdentificacion("registrado", carnet, "Estudiante identificado.")


def identificar_por_codigo(codigo, usuario):
    """Busca el carné por su hash. Si es nuevo, lo crea y lo completa con los datos del SGA (HU04)."""
    qr_hash = calcular_hash(codigo)
    carnet = CarnetEstudiantil.objects.select_related("estudiante").filter(qr_hash=qr_hash).first()

    if carnet is None:
        datos = _consultar_sga(codigo)  # fuera de la transacción: es una llamada de red
        if datos is not None and not datos.valido:
            # El SGA indica que el carné no es válido: no se registra ni se verifica.
            return ResultadoIdentificacion("no_valido_sga", None, "El SGA indica que este carné no es válido.")
        try:
            with transaction.atomic():
                estudiante = Estudiante.objects.create()
                carnet = CarnetEstudiantil.objects.create(
                    usuario_registro=usuario,
                    estudiante=estudiante,
                    qr_hash=qr_hash,
                    codigo_validacion=codigo,
                    estado_registro=CarnetEstudiantil.PENDIENTE,
                )
                if datos is not None:
                    _aplicar_datos_sga(carnet, datos)
        except IntegrityError:
            # Otro escaneo simultáneo ya creó el carné: se usa ese.
            carnet = CarnetEstudiantil.objects.select_related("estudiante").get(qr_hash=qr_hash)
            return _estado_carnet(carnet)
        resultado = _estado_carnet(carnet)
        if resultado.estado == "registrado":
            resultado = ResultadoIdentificacion("nuevo", carnet, "Carné nuevo registrado con los datos del SGA.")
        elif resultado.estado == "pendiente":
            resultado = ResultadoIdentificacion(
                "nuevo", carnet, "Carné nuevo registrado como pendiente: no se pudo consultar el SGA. Puede continuar con la verificación."
            )
        return resultado

    # Carné ya registrado pero pendiente: se reintenta la consulta al SGA.
    if carnet.estado_registro == CarnetEstudiantil.PENDIENTE and not carnet.estudiante.nombres:
        datos = _consultar_sga(codigo)
        if datos is not None and datos.valido:
            with transaction.atomic():
                _aplicar_datos_sga(carnet, datos)
    return _estado_carnet(carnet)


def identificar_por_qr(texto_qr, usuario):
    return identificar_por_codigo(extraer_codigo(texto_qr), usuario)


def ocultar_cedula(cedula):
    """Muestra solo los dos primeros y dos últimos dígitos (RNF06)."""
    if not cedula or len(cedula) < 5:
        return cedula
    return f"{cedula[:2]}{'•' * (len(cedula) - 4)}{cedula[-2:]}"
