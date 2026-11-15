"""Filtros para mostrar la materia y la práctica guardadas en la observación de la validación."""
from django import template

from verificacion.sesion_practica import separar

register = template.Library()


@register.filter
def materia(observacion):
    return separar(observacion)[0]


@register.filter
def practica(observacion):
    return separar(observacion)[1]
