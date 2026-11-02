from django.contrib import admin

from .models import CorreccionValidacion, Validacion, ValidacionDetalle


class DetalleInline(admin.TabularInline):
    model = ValidacionDetalle
    extra = 0
    can_delete = False
    readonly_fields = ["epp", "requerido", "detectado_modelo", "detectado_final", "confianza", "umbral_usado"]


@admin.register(Validacion)
class ValidacionAdmin(admin.ModelAdmin):
    """Consulta de apoyo. El registro y la corrección se hacen desde la aplicación."""

    list_display = ["id_validacion", "fecha_hora", "carnet", "laboratorio", "resultado_modelo", "resultado_final", "corregida"]
    list_filter = ["laboratorio", "periodo", "resultado_final", "corregida"]
    inlines = [DetalleInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CorreccionValidacion)
class CorreccionValidacionAdmin(admin.ModelAdmin):
    list_display = ["fecha", "detalle", "tipo_error", "valor_anterior", "valor_nuevo", "usuario"]
    list_filter = ["tipo_error"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
