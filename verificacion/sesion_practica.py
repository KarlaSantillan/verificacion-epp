"""Materia y práctica de la sesión de laboratorio (sugerencia de la tutora, asesoría del 12/11/2026).

Son datos descriptivos: el docente los escribe una vez al iniciar la sesión y se guardan en cada
validación que registre después. No intervienen en la evaluación del cumplimiento.

No se modifica la base de datos: se guardan como texto en la columna "observacion" de
EPP_T_VALIDACION, que ya existía y no se usaba, con el formato
    Materia: Microbiología | Práctica: Tinción de Gram
"""
import json
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

CLAVE_SESION = "sesion_practica"
LARGO_MATERIA = 100
LARGO_PRACTICA = 150
_FORMATO = re.compile(r"^Materia: (?P<materia>[^|]*?) ?\| Práctica: (?P<practica>.*)$", re.DOTALL)


def limpiar(texto, largo):
    """Quita espacios repetidos, el separador "|" y recorta al largo indicado."""
    return " ".join(str(texto or "").replace("|", "/").split())[:largo]


def componer(materia, practica):
    """Texto que se guarda en la observación ("" si no hay ninguno de los dos)."""
    materia, practica = limpiar(materia, LARGO_MATERIA), limpiar(practica, LARGO_PRACTICA)
    if not materia and not practica:
        return ""
    return f"Materia: {materia} | Práctica: {practica}"


def separar(observacion):
    """(materia, practica) a partir de la observación guardada."""
    coincidencia = _FORMATO.match(observacion or "")
    if coincidencia is None:
        return "", ""
    return coincidencia["materia"].strip(), coincidencia["practica"].strip()


def leer(request):
    """Materia y práctica guardadas en la sesión del docente ("" si no las escribió)."""
    datos = request.session.get(CLAVE_SESION) or {}
    return {"materia": datos.get("materia", ""), "practica": datos.get("practica", "")}


@login_required
@require_POST
def guardar(request):
    """Recibe {materia, practica} desde la pantalla de verificación y los deja en la sesión."""
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "mensaje": "Solicitud no válida."}, status=400)
    valores = {
        "materia": limpiar(datos.get("materia"), LARGO_MATERIA),
        "practica": limpiar(datos.get("practica"), LARGO_PRACTICA),
    }
    # Hora de inicio de la práctica, para el resumen de la clase. Se reinicia con «Empezar nueva práctica».
    previo = request.session.get(CLAVE_SESION) or {}
    inicio = None if datos.get("nueva") else previo.get("inicio")
    request.session[CLAVE_SESION] = {**valores, "inicio": inicio or timezone.now().isoformat()}
    return JsonResponse({"ok": True, **valores})
