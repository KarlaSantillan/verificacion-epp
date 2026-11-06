from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "auditoria"
    verbose_name = "Auditoría"

    def ready(self):
        from . import registro  # noqa: F401  (conecta las señales de auditoría automática, TK08)
