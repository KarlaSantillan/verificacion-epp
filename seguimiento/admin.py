from django.contrib import admin

from .models import LlamadoAtencion


@admin.register(LlamadoAtencion)
class LlamadoAtencionAdmin(admin.ModelAdmin):
    list_display = ["fecha_hora", "estudiante", "periodo", "cantidad_incidencias", "usuario"]
    list_filter = ["periodo"]
    search_fields = ["estudiante__nombres", "estudiante__apellidos", "estudiante__cedula"]

    def has_delete_permission(self, request, obj=None):
        return False
