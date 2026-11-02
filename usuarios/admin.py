from django import forms
from django.contrib import admin

from .models import Rol, Usuario
from django.contrib.auth.models import Group

admin.site.unregister(Group)
admin.site.site_header = "Verificación de EPP – Administración"
admin.site.site_title = "Verificación de EPP"
admin.site.index_title = "Panel de administración"


class UsuarioForm(forms.ModelForm):
    nueva_contrasena = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Obligatoria al crear el usuario. Al editar, déjela vacía para conservar la actual.",
    )

    class Meta:
        model = Usuario
        fields = ["nombres", "apellidos", "correo", "rol", "activo"]

    def clean(self):
        datos = super().clean()
        if not self.instance.pk and not datos.get("nueva_contrasena"):
            self.add_error("nueva_contrasena", "Ingrese una contraseña para el nuevo usuario.")
        return datos


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    form = UsuarioForm
    list_display = ["nombres", "apellidos", "correo", "rol", "activo", "fecha_creacion"]
    list_filter = ["rol", "activo"]
    search_fields = ["nombres", "apellidos", "correo"]

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get("nueva_contrasena"):
            obj.set_password(form.cleaned_data["nueva_contrasena"])
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False  # Los usuarios se desactivan, no se eliminan.


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ["nombre", "descripcion"]


