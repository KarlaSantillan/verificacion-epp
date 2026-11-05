from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def solo_administrador(vista):
    """Permite el acceso solo a usuarios con rol Administrador (HU01-CA03 / RF01-CA04).

    Un usuario sin sesión es enviado al inicio de sesión; un docente recibe
    la página de acceso denegado (403).
    """

    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.es_administrador:
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltura
