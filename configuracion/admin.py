from django.contrib import admin

from .models import Epp, Laboratorio, LaboratorioEpp, ModeloVision, Parametro, PeriodoAcademico


class LaboratorioEppInline(admin.TabularInline):
    """Permite configurar los EPP de cada laboratorio en la misma pantalla (HU12)."""

    model = LaboratorioEpp
    extra = 0
    can_delete = False
    fields = ["epp", "obligatorio", "confianza_minima", "activo"]


@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "ubicacion", "tiempo_estabilizacion_segundos", "activo"]
    list_filter = ["activo"]
    inlines = [LaboratorioEppInline]

    def has_delete_permission(self, request, obj=None):
        return False  # Se desactivan con la casilla "Activo", no se eliminan.

@admin.register(Epp)
class EppAdmin(admin.ModelAdmin):
    list_display = ["nombre", "clase_modelo", "activo"]
    list_filter = ["activo"]
    
    def has_delete_permission(self, request, obj=None):
        return False  # Se desactivan con la casilla "Activo", no se eliminan.

@admin.register(PeriodoAcademico)
class PeriodoAcademicoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "fecha_inicio", "fecha_fin"]


@admin.register(ModeloVision)
class ModeloVisionAdmin(admin.ModelAdmin):
    list_display = ["nombre", "version", "fecha_entrenamiento", "activo"]


@admin.register(Parametro)
class ParametroAdmin(admin.ModelAdmin):
    list_display = ["clave", "valor", "descripcion", "fecha_actualizacion"]
    readonly_fields = ["fecha_actualizacion"]

    def get_readonly_fields(self, request, obj=None):
        # La clave no se cambia una vez creada, porque el código la busca por su nombre.
        return ["clave", "fecha_actualizacion"] if obj else ["fecha_actualizacion"]
