from .contexto import fijar_usuario, restaurar_usuario


class UsuarioActualMiddleware:
    """Deja disponible el usuario de la petición para la auditoría automática (TK08)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = fijar_usuario(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            restaurar_usuario(token)
