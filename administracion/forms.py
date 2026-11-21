"""Formularios de las pantallas de administración (HU12 / HU13)."""
import re
from decimal import Decimal

from django import forms
from django.contrib.auth.password_validation import validate_password

from configuracion.models import Epp, Laboratorio, ModeloVision, Parametro, PeriodoAcademico
from estudiantes.forms import validar_cedula, validar_correo_unemi
from estudiantes.models import Estudiante
from usuarios.models import Rol, Usuario


class EstiloEpp:
    """Aplica las clases de Bootstrap a todos los campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


# ---------------------------------------------------------------- Laboratorios (HU12)

class LaboratorioForm(EstiloEpp, forms.ModelForm):
    class Meta:
        model = Laboratorio
        fields = ["nombre", "ubicacion", "descripcion", "tiempo_estabilizacion_segundos", "activo"]
        labels = {"ubicacion": "Ubicación", "descripcion": "Descripción", "tiempo_estabilizacion_segundos": "Tiempo de estabilización (s)"}
        widgets = {"descripcion": forms.TextInput()}

    def clean_tiempo_estabilizacion_segundos(self):
        valor = self.cleaned_data["tiempo_estabilizacion_segundos"]
        if not 1 <= valor <= 10:
            raise forms.ValidationError("Debe estar entre 1 y 10 segundos.")
        return valor


class RequisitosForm(forms.Form):
    """Requisitos de EPP de un laboratorio: habilitado, obligatorio y confianza mínima en % (HU12)."""

    def __init__(self, *args, epps, existentes, **kwargs):
        super().__init__(*args, **kwargs)
        self.epps = list(epps)
        for epp in self.epps:
            actual = existentes.get(epp.id_epp)
            self.fields[f"hab_{epp.id_epp}"] = forms.BooleanField(
                required=False, initial=bool(actual and actual.activo),
                widget=forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            )
            self.fields[f"obl_{epp.id_epp}"] = forms.BooleanField(
                required=False, initial=bool(actual and actual.activo and actual.obligatorio),
                widget=forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            )
            self.fields[f"conf_{epp.id_epp}"] = forms.IntegerField(
                min_value=1, max_value=100,
                initial=round(actual.confianza_minima * 100) if actual else 80,
                error_messages={"min_value": "Debe estar entre 1 y 100.", "max_value": "Debe estar entre 1 y 100.", "required": "Obligatorio."},
                widget=forms.NumberInput(attrs={"class": "form-control form-control-sm confianza", "min": 1, "max": 100}),
            )

    def filas(self):
        """Una fila por EPP para dibujar la tabla en la plantilla."""
        for epp in self.epps:
            yield {
                "epp": epp,
                "habilitado": self[f"hab_{epp.id_epp}"],
                "obligatorio": self[f"obl_{epp.id_epp}"],
                "confianza": self[f"conf_{epp.id_epp}"],
            }

    def requisitos(self):
        """[(epp, habilitado, obligatorio, confianza Decimal)] ya validados."""
        datos = self.cleaned_data
        for epp in self.epps:
            obligatorio = datos.get(f"obl_{epp.id_epp}", False)
            habilitado = datos.get(f"hab_{epp.id_epp}", False) or obligatorio  # obligatorio implica habilitado
            yield epp, habilitado, obligatorio, Decimal(datos[f"conf_{epp.id_epp}"]) / 100


# ---------------------------------------------------------------- Catálogo EPP

class EppForm(EstiloEpp, forms.ModelForm):
    class Meta:
        model = Epp
        fields = ["nombre", "clase_modelo", "descripcion", "activo"]
        labels = {"clase_modelo": "Clase del modelo", "descripcion": "Descripción"}
        help_texts = {"clase_modelo": "Debe coincidir con una clase del modelo YOLOv8 (ej.: gloves)."}
        widgets = {"descripcion": forms.TextInput()}

    def clean_clase_modelo(self):
        clase = self.cleaned_data["clase_modelo"].strip()
        if not re.fullmatch(r"[a-z0-9_]+", clase):
            raise forms.ValidationError("Use solo minúsculas, números y guion bajo, igual que en el modelo.")
        repetida = Epp.objects.filter(clase_modelo=clase).exclude(pk=self.instance.pk).exists()
        if repetida:
            raise forms.ValidationError("Ya existe un EPP con esa clase del modelo.")
        return clase


# ---------------------------------------------------------------- Estudiantes

class EstudianteForm(EstiloEpp, forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = ["nombres", "apellidos", "cedula", "correo", "carrera", "facultad", "modalidad", "nivel", "activo"]
        labels = {"cedula": "Cédula (opcional)", "correo": "Correo institucional (opcional)"}
        help_texts = {"correo": "Se usa para notificar al estudiante cuando se registra un llamado de atención."}

    def clean_cedula(self):
        return validar_cedula(self.cleaned_data.get("cedula")) or None

    def clean_correo(self):
        return validar_correo_unemi(self.cleaned_data.get("correo")) or None


# ---------------------------------------------------------------- Usuarios (HU13-CA02)

class UsuarioForm(EstiloEpp, forms.ModelForm):
    contrasena = forms.CharField(label="Contraseña", required=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    confirmacion = forms.CharField(label="Confirmar contraseña", required=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = Usuario
        fields = ["nombres", "apellidos", "correo", "rol", "activo"]
        labels = {"correo": "Correo institucional"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rol"].queryset = Rol.objects.order_by("nombre")
        self.fields["rol"].empty_label = None
        nuevo = self.instance.pk is None
        self.fields["contrasena"].required = nuevo
        self.fields["confirmacion"].required = nuevo
        self.fields["contrasena"].label = "Contraseña inicial" if nuevo else "Nueva contraseña (opcional)"
        self.fields["contrasena"].help_text = "Mínimo 8 caracteres. Se guarda cifrada; nunca se muestra."

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if Usuario.objects.filter(correo__iexact=correo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un usuario con ese correo.")
        return correo

    def clean(self):
        datos = super().clean()
        contrasena, confirmacion = datos.get("contrasena"), datos.get("confirmacion")
        if contrasena or confirmacion:
            if contrasena != confirmacion:
                self.add_error("confirmacion", "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(contrasena, self.instance)
                except forms.ValidationError as error:
                    self.add_error("contrasena", error)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get("contrasena"):
            usuario.set_password(self.cleaned_data["contrasena"])
        if commit:
            usuario.save()
        return usuario


# ---------------------------------------------------------------- Periodos (RF15-CA04)

class PeriodoForm(EstiloEpp, forms.ModelForm):
    class Meta:
        model = PeriodoAcademico
        fields = ["nombre", "fecha_inicio", "fecha_fin"]
        labels = {"fecha_inicio": "Fecha de inicio", "fecha_fin": "Fecha de fin"}
        widgets = {"fecha_inicio": FECHA, "fecha_fin": FECHA, "nombre": forms.TextInput(attrs={"placeholder": "Agosto - Diciembre 2026"})}

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("fecha_inicio"), datos.get("fecha_fin")
        if inicio and fin and fin <= inicio:
            self.add_error("fecha_fin", "La fecha de fin debe ser posterior al inicio.")
        return datos


# ---------------------------------------------------------------- Parámetros (HU13-CA04)

AYUDA_PARAMETROS = {
    "umbral_incidencias": "Número entero entre 1 y 20.",
    "prefijo_qr_valido": 'Debe empezar con "https://" y no contener espacios.',
}


class ParametroForm(EstiloEpp, forms.ModelForm):
    class Meta:
        model = Parametro
        fields = ["valor"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["valor"].help_text = AYUDA_PARAMETROS.get(self.instance.clave, "")
        if self.instance.clave == "umbral_incidencias":
            self.fields["valor"].widget = forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 20, "step": 1})

    def clean_valor(self):
        valor = self.cleaned_data["valor"].strip()
        clave = self.instance.clave
        if clave == "umbral_incidencias":
            if not valor.isdigit() or not 1 <= int(valor) <= 20:
                raise forms.ValidationError("Debe ser un número entero entre 1 y 20.")
        elif clave == "prefijo_qr_valido":
            if not re.fullmatch(r"https://\S+", valor):
                raise forms.ValidationError('Debe empezar con "https://" y no contener espacios.')
        elif not valor:
            raise forms.ValidationError("El valor es obligatorio.")
        return valor


# ---------------------------------------------------------------- Modelo de visión (HU13-CA03)

class ModeloVisionForm(EstiloEpp, forms.ModelForm):
    class Meta:
        model = ModeloVision
        fields = ["nombre", "version", "dataset_entrenamiento", "fecha_entrenamiento"]
        labels = {"version": "Versión", "dataset_entrenamiento": "Dataset de entrenamiento", "fecha_entrenamiento": "Fecha de entrenamiento"}
        help_texts = {"version": "El archivo debe estar en modelos/epp_<versión>.pt (ej.: v2 → modelos/epp_v2.pt)."}
        widgets = {"fecha_entrenamiento": FECHA}

    def clean_version(self):
        version = self.cleaned_data["version"].strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", version):
            raise forms.ValidationError("Use solo letras, números, punto, guion o guion bajo (se usa en el nombre del archivo).")
        return version
