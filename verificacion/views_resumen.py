"""Resumen de la clase que termina (al pulsar «Nueva práctica») y su envío por correo al docente."""
import logging
from datetime import datetime
from email.utils import formataddr

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import resumen_practica
from usuarios.models import Usuario

from .sesion_practica import CLAVE_SESION, leer

logger = logging.getLogger(__name__)


def _fecha(texto):
    try:
        valor = datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        raise Http404
    return timezone.make_aware(valor) if timezone.is_naive(valor) else valor


def _docente(request, id_docente):
    """El docente solo ve sus prácticas; el administrador puede ver las de cualquiera."""
    if not id_docente or str(id_docente) == str(request.user.pk):
        return request.user
    if not request.user.es_administrador or not str(id_docente).isdigit():
        raise Http404
    docente = Usuario.objects.filter(pk=int(id_docente)).first()
    if docente is None:
        raise Http404
    return docente


def _resumen(request, parametros=None):
    p = parametros or {}
    if p.get("desde"):  # una práctica anterior (sección «Mis prácticas»)
        return resumen_practica.calcular(
            _docente(request, p.get("docente")), p.get("materia", ""), p.get("practica", ""),
            _fecha(p["desde"]), _fecha(p["hasta"]) if p.get("hasta") else None,
        )
    datos = leer(request)
    desde = resumen_practica.inicio_de_practica(request.session.get(CLAVE_SESION))
    return resumen_practica.calcular(request.user, datos["materia"], datos["practica"], desde)


@login_required
@require_GET
def ver(request):
    resumen = _resumen(request)
    return JsonResponse({
        "total": resumen.total,
        "html": render_to_string("verificacion/_resumen_practica.html", {"r": resumen}, request=request),
    })


@login_required
@require_GET
def imprimir(request):
    """Documento con formato de guía de práctica, para imprimir o guardar como PDF desde el navegador."""
    contexto = {"r": _resumen(request, request.GET), "emitido": timezone.now(), "imprimir": request.GET.get("imprimir") == "1"}
    return render(request, "verificacion/resumen_practica_imprimir.html", contexto)


def _texto(r):
    lineas = [
        "Resumen de la práctica de laboratorio",
        "",
        f"Materia: {r.materia or '—'}",
        f"Práctica: {r.practica or '—'}",
        f"Laboratorio: {', '.join(r.laboratorios) or '—'}",
        f"Docente: {r.docente}",
    ]
    if r.inicio:
        lineas.append(f"Horario: {timezone.localtime(r.inicio):%d/%m/%Y %H:%M} – {timezone.localtime(r.fin):%H:%M}")
    lineas += [
        "",
        f"Estudiantes verificados: {r.total}",
        f"Cumplieron: {r.cumplieron} ({r.porcentaje} %)",
        f"No cumplieron: {len(r.no_cumplieron)}",
        f"Corrigieron sus EPP en el momento: {r.corrigieron}",
    ]
    if r.epp_faltantes:
        lineas.append(f"EPP que faltaron (veces): {r.resumen_faltantes}")
    if r.no_cumplieron:
        lineas += ["", "Estudiantes que no cumplieron:"]
        lineas += [f"- {e.nombre}: falta {', '.join(e.faltantes) or '—'}" for e in r.no_cumplieron]
    lineas += ["", "Mensaje generado automáticamente por el Sistema de Verificación de EPP."]
    return "\n".join(lineas)


@login_required
@require_POST
def enviar(request):
    """Envía el resumen al correo del usuario que inició sesión. Nunca bloquea el cambio de práctica."""
    resumen = _resumen(request, request.POST)
    if not resumen.total:
        return JsonResponse({"ok": False, "mensaje": "No hay verificaciones en esta práctica."}, status=400)
    destino = request.user.correo
    remitente = getattr(settings, "CORREO_REMITENTE", None)
    nombre = getattr(settings, "CORREO_NOMBRE", "Sistema de Verificación de EPP")
    asunto = f"Resumen de la práctica: {resumen.materia or 'Laboratorio'}{' – ' + resumen.practica if resumen.practica else ''}"
    mensaje = EmailMultiAlternatives(
        subject=asunto,
        body=_texto(resumen),
        from_email=formataddr((nombre, remitente)) if remitente else None,
        to=[destino],
    )
    mensaje.attach_alternative(render_to_string("correo/resumen_practica.html", {"r": resumen}), "text/html")
    try:
        mensaje.send()
    except Exception:
        logger.exception("No se pudo enviar el resumen de la práctica a %s", destino)
        return JsonResponse({"ok": False, "mensaje": "No se pudo enviar el correo. Revise la conexión a internet."}, status=502)
    return JsonResponse({"ok": True, "mensaje": f"Resumen enviado a {destino}."})
