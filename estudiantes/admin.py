from django.contrib import admin

from .models import CarnetEstudiantil, Estudiante


class CarnetInline(admin.TabularInline):
    model = CarnetEstudiantil
    extra = 0
    fields = ["codigo_validacion", "estado_registro", "fecha_fin_vigencia", "activo"]
    readonly_fields = ["codigo_validacion"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # Los carnés se crean al leer el QR en la verificación.


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ["__str__", "cedula", "carrera", "nivel", "activo"]
    search_fields = ["nombres", "apellidos", "cedula"]
    list_filter = ["activo", "carrera"]
    inlines = [CarnetInline]


@admin.register(CarnetEstudiantil)
class CarnetEstudiantilAdmin(admin.ModelAdmin):
    list_display = ["codigo_validacion", "estudiante", "estado_registro", "fecha_fin_vigencia", "usuario_registro", "activo"]
    list_filter = ["estado_registro", "activo"]
    search_fields = ["codigo_validacion", "estudiante__nombres", "estudiante__apellidos", "estudiante__cedula"]
    readonly_fields = ["qr_hash", "fecha_creacion"]

    def has_add_permission(self, request):
        return False  # Los carnés se crean al leer el QR en la verificación.

    def has_delete_permission(self, request, obj=None):
        return False
