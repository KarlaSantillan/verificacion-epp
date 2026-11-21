"""Notificación por correo del llamado de atención (HU16 / RF13, pedido en la tutoría).

- Se envía cuando el docente registra el llamado (no al llegar al umbral): el docente revisa el caso
  antes de notificar y el correo lleva su observación. Un llamado se registra una sola vez.
- Si no hay internet o Gmail no responde, el llamado igual queda guardado y el docente puede
  reenviar la notificación después desde el historial del estudiante (RNF10: tolerancia a fallos).
- Cada intento (enviado, sin correo o error) queda en la auditoría (RNF07: trazabilidad), sin
  cambiar la base de datos.
- Por la LOPDP, el mensaje no incluye la cédula ni imágenes, y la auditoría guarda el correo enmascarado.
"""
import logging
from collections import Counter
from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from auditoria.models import Auditoria
from estudiantes.servicios import ocultar_correo
from verificacion.models import Validacion

logger = logging.getLogger(__name__)

ENVIADO = "enviado"
SIN_CORREO = "sin_correo"
ERROR = "error"

ACCION_AUDITORIA = "NOTIFICACION"
TABLA_LLAMADO = "epp_t_llamado_atencion"
ASUNTO = "Llamado de atención por uso de EPP en el laboratorio"
DESCRIPCIONES = {
    ENVIADO: "Notificación del llamado enviada por correo al estudiante.",
    SIN_CORREO: "No se envió la notificación: el estudiante no tiene correo registrado.",
    ERROR: "No se pudo enviar la notificación por correo (sin conexión o error del servidor de correo).",
}


def faltantes_hasta(llamado):
    """EPP que faltaron en las incidencias del periodo hasta el llamado: «Mascarilla (3), Bata (2)»."""
    incidencias = (
        Validacion.objects.filter(
            carnet__estudiante=llamado.estudiante, periodo=llamado.periodo,
            resultado_final=Validacion.NO_CONFORME, fecha_hora__lte=llamado.fecha_hora,
        )
        .prefetch_related("detalles__epp")
    )
    conteo = Counter(d.epp.nombre for v in incidencias for d in v.detalles.all() if d.requerido and not d.detectado_final)
    return ", ".join(f"{nombre} ({veces})" for nombre, veces in conteo.most_common())


def datos_notificacion(llamado, faltantes=None):
    """Datos comunes del correo en texto y en HTML."""
    usuario = llamado.usuario
    return {
        "estudiante": str(llamado.estudiante),
        "periodo": llamado.periodo.nombre,
        "incidencias": llamado.cantidad_incidencias,
        "faltantes": faltantes,
        "fecha": timezone.localtime(llamado.fecha_hora).strftime("%d/%m/%Y %H:%M"),
        "docente": f"{usuario.nombres or ''} {usuario.apellidos or ''}".strip() or usuario.correo,
        "observacion": llamado.observacion,
    }


def texto_notificacion(llamado, faltantes=None):
    """Versión en texto plano: la ven los lectores de correo que no muestran HTML."""
    d = datos_notificacion(llamado, faltantes)
    estudiante, docente, fecha = d["estudiante"], d["docente"], d["fecha"]
    lineas = [
        f"Estimado/a {estudiante}:",
        "",
        "Le informamos que se registró un llamado de atención por no cumplir con el equipo de protección "
        "personal (EPP) exigido en los laboratorios de Biotecnología de la UNEMI.",
        "",
        f"Periodo académico: {llamado.periodo.nombre}",
        f"Incidencias registradas: {llamado.cantidad_incidencias}",
    ]
    if faltantes:
        lineas.append(f"EPP que le faltaron (número de veces): {faltantes}")
    lineas += [
        f"Fecha del llamado: {fecha}",
        f"Registrado por: {docente}",
        "",
        "Observación del docente:",
        llamado.observacion,
        "",
        "Recuerde ingresar con todos los EPP requeridos, según el Protocolo de Bioseguridad de los laboratorios.",
        "",
        "Este mensaje fue generado automáticamente por el sistema de verificación de EPP. No responda a este correo.",
    ]
    return "\n".join(lineas)


def _auditar(llamado, usuario, estado, correo):
    try:
        Auditoria.objects.create(
            usuario=usuario,
            tipo_actor=Auditoria.USUARIO if usuario else Auditoria.SISTEMA,
            tabla_afectada=TABLA_LLAMADO,
            id_registro_afectado=llamado.pk,
            accion=ACCION_AUDITORIA,
            datos_nuevos={"resultado": estado, "correo": ocultar_correo(correo) if correo else None},
            descripcion=DESCRIPCIONES[estado],
        )
    except Exception:  # la auditoría de la notificación nunca debe romper el llamado
        logger.exception("No se pudo auditar la notificación del llamado %s", llamado.pk)


def notificar_llamado(llamado, usuario=None, faltantes=None):
    """Envía el correo al estudiante. Devuelve ENVIADO, SIN_CORREO o ERROR; nunca lanza excepción."""
    correo = llamado.estudiante.correo
    if not correo:
        _auditar(llamado, usuario, SIN_CORREO, None)
        return SIN_CORREO
    if faltantes is None:
        faltantes = faltantes_hasta(llamado)
    remitente = getattr(settings, "CORREO_REMITENTE", None)
    nombre = getattr(settings, "CORREO_NOMBRE", "Sistema de Verificación de EPP")
    mensaje = EmailMultiAlternatives(
        subject=ASUNTO,
        body=texto_notificacion(llamado, faltantes),
        from_email=formataddr((nombre, remitente)) if remitente else None,
        to=[correo],
    )
    # Versión con formato (encabezado azul oscuro y detalles en amarillo); el texto plano queda como respaldo.
    mensaje.attach_alternative(render_to_string("correo/llamado_atencion.html", datos_notificacion(llamado, faltantes)), "text/html")
    try:
        mensaje.send()
    except Exception:  # sin internet, SMTP caído, credenciales erróneas...: el llamado ya está guardado
        logger.exception("No se pudo enviar la notificación del llamado %s", llamado.pk)
        _auditar(llamado, usuario, ERROR, correo)
        return ERROR
    _auditar(llamado, usuario, ENVIADO, correo)
    return ENVIADO


def estado_de_notificaciones(llamados):
    """{id_llamado: último resultado (ENVIADO, SIN_CORREO o ERROR)} según la auditoría."""
    ids = [l.pk for l in llamados]
    estados = {}
    eventos = Auditoria.objects.filter(
        tabla_afectada=TABLA_LLAMADO, accion=ACCION_AUDITORIA, id_registro_afectado__in=ids
    ).order_by("fecha_hora", "pk")
    for evento in eventos:
        estados[evento.id_registro_afectado] = (evento.datos_nuevos or {}).get("resultado")
    return estados
