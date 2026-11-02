from django.contrib import admin

from .models import Auditoria


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    """Bitácora de solo lectura (RF16-CA03): no se puede crear, editar ni eliminar."""

    list_display = ["fecha_hora", "tipo_actor", "usuario", "accion", "tabla_afectada", "id_registro_afectado"]
    list_filter = ["accion", "tipo_actor", "tabla_afectada"]
    search_fields = ["descripcion", "tabla_afectada"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
