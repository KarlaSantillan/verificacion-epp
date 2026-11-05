from django import forms

def validar_cedula(valor):
    """Cédula ecuatoriana: 10 dígitos. Vacía se permite."""
    cedula = "".join((valor or "").split())
    if cedula and (not cedula.isdigit() or len(cedula) != 10):
        raise forms.ValidationError("La cédula debe tener 10 dígitos.")
    return cedula

class CompletarCarnetForm(forms.Form):
    """Datos que el docente copia de la página de validación del SGA (HU05)."""

    nombres = forms.CharField(max_length=120)
    apellidos = forms.CharField(max_length=120)
    cedula = forms.CharField(
        label="Cédula (opcional)", max_length=10, required=False,
        help_text="Solo si el estudiante la proporciona. Sirve para no duplicar estudiantes que ya tienen otro carné.",
    )
    carrera = forms.CharField(max_length=120, required=False)
    facultad = forms.CharField(max_length=120, required=False)
    modalidad = forms.CharField(max_length=30, required=False)
    nivel = forms.CharField(max_length=50, required=False)
    fecha_fin_vigencia = forms.DateField(
        label="Fin de vigencia del carné", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")

    def clean_cedula(self):
        return validar_cedula(self.cleaned_data.get("cedula"))

    def clean_nombres(self):
        return self.cleaned_data["nombres"].strip().title()

    def clean_apellidos(self):
        return self.cleaned_data["apellidos"].strip().title()
