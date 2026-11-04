from django.contrib import admin
from django.utils.html import format_html

from .models import CarnetEstudiantil, Estudiante
from .sga import url_validacion


def enlace_sga(carnet):
    """Enlace a la página oficial de validación, para revisar a mano los carnés pendientes (HU05)."""
    if not carnet or not carnet.codigo_validacion:
        return "—"
    return format_html('<a href="{}" target="_blank" rel="noopener">Ver validación en SGA ↗</a>', url_validacion(carnet.codigo_validacion))


class CarnetInline(admin.TabularInline):
    model = CarnetEstudiantil
    extra = 0
    can_delete = False
    fields = ["codigo_validacion", "validacion_sga", "estado_registro", "fecha_fin_vigencia", "activo"]
    readonly_fields = ["codigo_validacion", "validacion_sga"]

    @admin.display(description="Validación SGA")
    def validacion_sga(self, obj):
        return enlace_sga(obj)

    def has_add_permission(self, request, obj=None):
        return False  # Los carnés se crean al leer el QR en la verificación.


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ["__str__", "cedula", "carrera", "nivel", "activo"]
    search_fields = ["nombres", "apellidos", "cedula"]
    list_filter = ["activo", "carrera"]
    inlines = [CarnetInline]

    def has_delete_permission(self, request, obj=None):
        return False  # Se desactivan con la casilla "Activo", no se eliminan.


@admin.register(CarnetEstudiantil)
class CarnetEstudiantilAdmin(admin.ModelAdmin):
    list_display = ["codigo_validacion", "estudiante", "estado_registro", "fecha_fin_vigencia", "usuario_registro", "activo"]
    list_filter = ["estado_registro", "activo"]
    search_fields = ["codigo_validacion", "estudiante__nombres", "estudiante__apellidos", "estudiante__cedula"]
    readonly_fields = ["qr_hash", "fecha_creacion", "validacion_sga"]

    @admin.display(description="Validación SGA")
    def validacion_sga(self, obj):
        return enlace_sga(obj)

    def has_add_permission(self, request):
        return False  # Los carnés se crean al leer el QR en la verificación.

    def has_delete_permission(self, request, obj=None):
        return False
