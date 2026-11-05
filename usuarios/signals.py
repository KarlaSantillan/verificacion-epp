from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from auditoria.models import Auditoria


@receiver(user_logged_in)
def registrar_inicio_sesion(sender, request, user, **kwargs):
    """Registra cada inicio de sesión en la auditoría (RF01-CA05)."""
    Auditoria.objects.create(
        usuario=user,
        tipo_actor=Auditoria.USUARIO,
        tabla_afectada="epp_m_usuario",
        id_registro_afectado=user.pk,
        accion="LOGIN",
        descripcion="Inicio de sesión",
    )
