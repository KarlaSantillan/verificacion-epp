"""Guardar el resultado de la verificación (HU08 / RF07)."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from auditoria.contexto import como_sistema
from configuracion.models import Laboratorio
from estudiantes.models import CarnetEstudiantil

from .evaluacion import SinRequisitos, evaluar
from .models import Validacion
from .registro import RegistroNoPermitido, registrar_validacion

CLAVE_SESION = "registros_validacion"  # clave de cada evaluación → id de la validación ya guardada


def _error(mensaje, codigo=400):
    return JsonResponse({"ok": False, "mensaje": mensaje}, status=codigo)


def _respuesta(validacion, repetido=False):
    conforme = validacion.resultado_final == Validacion.CONFORME
    return JsonResponse({
        "ok": True,
        "id": validacion.id_validacion,
        "resultado": validacion.resultado_final,
        "mensaje": "Ingreso registrado." if conforme else "Intento no conforme registrado como incidencia.",
        "repetido": repetido,
    })


@login_required
@require_POST
def registrar(request):
    """Recibe {clave, carnet, laboratorio, confianzas, confirmar_no_conforme}.

    - El resultado lo vuelve a calcular el servidor con evaluar(): no se confía en lo que diga el navegador.
    - "Cumple" se registra automáticamente (CA01) con el actor "Sistema" en la auditoría (RF16-CA02).
    - "No cumple" solo se registra si el docente lo confirma con el botón (CA02).
    - Con la misma clave no se crea un segundo registro: el reintento devuelve el que ya existe (CA04).
    """
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("Solicitud no válida.")

    clave = str(datos.get("clave") or "")[:64]
    if not clave:
        return _error("Falta la clave de la evaluación.")
    registrados = request.session.get(CLAVE_SESION, {})
    if clave in registrados:
        previa = Validacion.objects.filter(pk=registrados[clave]).first()
        if previa is not None:
            return _respuesta(previa, repetido=True)

    carnet = CarnetEstudiantil.objects.select_related("estudiante").filter(pk=datos.get("carnet"), activo=True).first()
    if carnet is None:
        return _error("El carné no existe o está inactivo.")
    laboratorio = Laboratorio.objects.filter(pk=datos.get("laboratorio"), activo=True).first()
    if laboratorio is None:
        return _error("El laboratorio no existe o está inactivo.")
    if not isinstance(datos.get("confianzas"), dict):
        return _error("Faltan las confianzas detectadas.")

    try:
        evaluacion = evaluar(laboratorio, datos["confianzas"])
    except SinRequisitos as error:
        return _error(str(error))

    if not evaluacion.cumple and not datos.get("confirmar_no_conforme"):
        return _error("Un resultado “No cumple” se registra solo al confirmarlo con el botón.")

    try:
        if evaluacion.cumple:
            with como_sistema():  # registro automático, sin intervención del docente
                validacion = registrar_validacion(usuario=request.user, carnet=carnet, laboratorio=laboratorio, evaluacion=evaluacion)
        else:
            validacion = registrar_validacion(usuario=request.user, carnet=carnet, laboratorio=laboratorio, evaluacion=evaluacion)
    except RegistroNoPermitido as error:
        return _error(str(error))

    registrados[clave] = validacion.id_validacion
    request.session[CLAVE_SESION] = dict(list(registrados.items())[-50:])  # se guardan solo las últimas 50
    return _respuesta(validacion)
