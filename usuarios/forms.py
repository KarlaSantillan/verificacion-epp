from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    """Formulario de inicio de sesión con correo y contraseña (HU01)."""

    username = forms.EmailField(
        label="Correo institucional",
        widget=forms.EmailInput(
            attrs={"class": "form-control form-control-lg", "placeholder": "nombre@unemi.edu.ec", "autocomplete": "username", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control form-control-lg", "autocomplete": "current-password"}),
    )

    # Mensaje genérico: no indica si falló el correo o la contraseña (HU01-CA02).
    # Un usuario desactivado recibe el mismo mensaje (HU01-CA02 / RF01-CA03).
    error_messages = {
        "invalid_login": "Correo o contraseña incorrectos.",
        "inactive": "Correo o contraseña incorrectos.",
    }
