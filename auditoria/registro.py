"""Auditoría automática de los cambios en los datos (TK08 / RF16-CA01, CA02, RNF07).

Cada vez que se guarda un registro de las tablas auditadas se crea un evento con:
- la acción: INSERT (nuevo), UPDATE (cambio) o DELETE (desactivación: activo pasa a False),
- los datos anteriores y los nuevos (solo los campos que cambiaron),
- el actor: el usuario de la sesión o "Sistema".

Datos sensibles: la contraseña y el hash del QR nunca se copian; la cédula se guarda enmascarada (RNF06).
Nota: QuerySet.update() no dispara estas señales; en el código se usa .save() para lo que deba auditarse.
"""
from datetime import date, datetime
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save

from configuracion.models import Epp, Laboratorio, LaboratorioEpp, ModeloVision, Parametro, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil, Estudiante
from seguimiento.models import LlamadoAtencion
from usuarios.models import Rol, Usuario
from verificacion.models import CorreccionValidacion, Validacion

from .contexto import usuario_actual
from .models import Auditoria

AUDITADOS = [
    Usuario, Rol, Laboratorio, LaboratorioEpp, Epp, PeriodoAcademico, Parametro, ModeloVision,
    Estudiante, CarnetEstudiantil, Validacion, CorreccionValidacion, LlamadoAtencion,
]
OMITIDOS = {"password_hash", "qr_hash", "fecha_creacion", "fecha_actualizacion", "last_login"}
OCULTOS = {"password_hash"}  # se informa que cambió, sin el valor


def _valor(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def _enmascarar(campo, valor):
    if campo == "cedula" and valor and len(valor) > 4:
        return f"{valor[:2]}{'•' * (len(valor) - 4)}{valor[-2:]}"
    return valor


def foto(instancia):
    """Datos del registro como diccionario, con los nombres de columna de la base (id_rol, activo...)."""
    datos = {}
    for campo in instancia._meta.concrete_fields:
        if campo.primary_key or campo.column in OMITIDOS:
            continue
        datos[campo.column] = _enmascarar(campo.column, _valor(getattr(instancia, campo.attname)))
    return datos


def _anterior(sender, instance, **kwargs):
    """Antes de guardar: se lee cómo estaba el registro en la base."""
    instance._auditoria_antes = None
    instance._auditoria_clave_cambio = False
    if instance.pk is None:
        return
    previo = sender.objects.filter(pk=instance.pk).first()
    if previo is not None:
        instance._auditoria_antes = foto(previo)
        if "password_hash" in OCULTOS and hasattr(previo, "password"):
            instance._auditoria_clave_cambio = previo.password != instance.password


def _crear_evento(instance, accion, antes, despues, descripcion):
    usuario = usuario_actual()
    Auditoria.objects.create(
        usuario=usuario,
        tipo_actor=Auditoria.USUARIO if usuario else Auditoria.SISTEMA,
        tabla_afectada=instance._meta.db_table,
        id_registro_afectado=instance.pk,
        accion=accion,
        datos_anteriores=antes,
        datos_nuevos=despues,
        descripcion=descripcion,
    )


def _guardado(sender, instance, created, **kwargs):
    nombre = instance._meta.verbose_name
    despues = foto(instance)
    antes_completo = getattr(instance, "_auditoria_antes", None)

    if created or antes_completo is None:
        _crear_evento(instance, "INSERT", None, despues, f"Creación de {nombre}: {instance}")
        return

    cambiados = [k for k in despues if antes_completo.get(k) != despues.get(k)]
    clave = getattr(instance, "_auditoria_clave_cambio", False)
    if not cambiados and not clave:
        return  # se guardó sin cambios: no se registra nada

    antes = {k: antes_completo.get(k) for k in cambiados}
    nuevos = {k: despues.get(k) for k in cambiados}
    if clave:
        antes["contrasena"], nuevos["contrasena"] = "••••", "cambiada"

    if cambiados == ["activo"] and antes["activo"] is True and nuevos["activo"] is False:
        _crear_evento(instance, "DELETE", antes, nuevos, f"Desactivación de {nombre}: {instance}")
    else:
        _crear_evento(instance, "UPDATE", antes, nuevos, f"Modificación de {nombre}: {instance}")


def _eliminado(sender, instance, **kwargs):
    _crear_evento(instance, "DELETE", foto(instance), None, f"Eliminación de {instance._meta.verbose_name}: {instance}")


for _modelo in AUDITADOS:
    pre_save.connect(_anterior, sender=_modelo, dispatch_uid=f"auditoria_pre_{_modelo.__name__}")
    post_save.connect(_guardado, sender=_modelo, dispatch_uid=f"auditoria_post_{_modelo.__name__}")
    post_delete.connect(_eliminado, sender=_modelo, dispatch_uid=f"auditoria_del_{_modelo.__name__}")
