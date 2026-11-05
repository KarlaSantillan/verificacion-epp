"""Etiquetas para las pantallas de administración (diseño del prototipo de Figma)."""
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Íconos de los cuatro EPP iniciales (los mismos SVG del prototipo; no existen en Bootstrap Icons).
_TRAZOS = {
    "lab_coat": '<path d="M9 3 6 5 4 12l2 1v8h12v-8l2-1-2-7-3-2"/><path d="M9 3l3 5 3-5M12 8v13"/>',
    "gloves": '<path d="M7 21v-5L4.5 12a1.5 1.5 0 0 1 2.4-1.8L8 11.5V5a1.3 1.3 0 0 1 2.6 0v5-6.5a1.3 1.3 0 0 1 2.6 0V10 4.5a1.3 1.3 0 0 1 2.6 0V10 6.5a1.3 1.3 0 0 1 2.6 0V15l-2 6Z"/>',
    "safety_glasses": '<path d="M2 10h20M3 10v3a3 3 0 0 0 3 3h2a3 3 0 0 0 3-2.5h2A3 3 0 0 0 16 16h2a3 3 0 0 0 3-3v-3"/>',
    "mask": '<path d="M5 9c3-1.5 11-1.5 14 0v4c0 3-3.5 5-7 5s-7-2-7-5Z"/><path d="M5 10H3v2l2 1M19 10h2v2l-2 1M9 12h6M9 14.5h6"/>',
}
_OTRO = '<path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6Z"/>'


@register.simple_tag
def epp_icono(clase, tamano=24):
    trazo = _TRAZOS.get(clase, _OTRO)
    return mark_safe(
        f'<svg viewBox="0 0 24 24" width="{int(tamano)}" height="{int(tamano)}" aria-hidden="true" fill="none" '
        f'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{trazo}</svg>'
    )


@register.simple_tag
def estado(activo, si="Activo", no="Inactivo"):
    if activo:
        return format_html('<span class="estado on"><i class="bi bi-check-circle"></i> {}</span>', si)
    return format_html('<span class="estado"><i class="bi bi-dash-circle"></i> {}</span>', no)


@register.inclusion_tag("administracion/_interruptor.html", takes_context=True)
def interruptor(context, tipo, objeto_id, activo, etiqueta):
    """Interruptor Activo/Inactivo: desactiva en lugar de eliminar (HU13-CA01)."""
    solicitud = context.get("request")
    return {
        "tipo": tipo, "objeto_id": objeto_id, "activo": activo, "etiqueta": etiqueta,
        "csrf_token": context.get("csrf_token"),
        "siguiente": solicitud.get_full_path() if solicitud else "",
    }


@register.filter
def porcentaje(valor):
    try:
        return f"{round(float(valor) * 100)} %"
    except (TypeError, ValueError):
        return "—"
