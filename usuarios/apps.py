from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "usuarios"
    verbose_name = "Usuarios y roles"

    def ready(self):
        from . import signals  # noqa: F401  (conecta el registro de inicios de sesión)
