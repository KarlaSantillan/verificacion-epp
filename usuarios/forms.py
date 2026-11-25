from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    _unicode_ci_compare,
)


class LoginForm(AuthenticationForm):
    """Formulario de inicio de sesión con correo y contraseña (HU01).

    Si en la pantalla anterior se eligió un perfil (Docente o Administrador),
    se comprueba que la cuenta corresponda a ese perfil. El mensaje es genérico
    para no revelar si falló el correo, la contraseña o el perfil (HU01-CA02).
    """

    PERFIL_DOCENTE = "docente"
    PERFIL_ADMIN = "administrador"
    PERFILES = (
        (PERFIL_DOCENTE, "Docente/Encargado"),
        (PERFIL_ADMIN, "Administrador"),
    )

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
    # Perfil elegido en la pantalla de selección. Opcional: si no se eligió
    # ninguno (por ejemplo, sin JavaScript), el inicio de sesión funciona igual.
    perfil = forms.ChoiceField(choices=PERFILES, required=False, widget=forms.HiddenInput())

    # Mensaje genérico: no indica si falló el correo o la contraseña (HU01-CA02).
    # Un usuario desactivado recibe el mismo mensaje (HU01-CA02 / RF01-CA03).
    error_messages = {
        "invalid_login": "Correo o contraseña incorrectos.",
        "inactive": "Correo o contraseña incorrectos.",
    }

    def clean(self):
        cleaned = super().clean()
        # Solo se valida el perfil si la autenticación fue correcta y se eligió uno.
        perfil = self.cleaned_data.get("perfil")
        usuario = self.get_user()
        if usuario and perfil:
            es_admin = usuario.es_administrador
            corresponde = (perfil == self.PERFIL_ADMIN and es_admin) or (perfil == self.PERFIL_DOCENTE and not es_admin)
            if not corresponde:
                raise forms.ValidationError(self.error_messages["invalid_login"], code="invalid_login")
        return cleaned


class RecuperarContrasenaForm(PasswordResetForm):
    """Pide el correo institucional para enviar el enlace de recuperación (RF01).

    Django solo envía el enlace a cuentas activas con ese correo. Si el correo
    no existe, no se revela: se muestra la misma pantalla de confirmación, de
    modo que no se puede enumerar qué cuentas existen.
    """

    email = forms.EmailField(
        label="Correo institucional",
        max_length=254,
        widget=forms.EmailInput(
            attrs={"class": "form-control form-control-lg", "placeholder": "nombre@unemi.edu.ec", "autocomplete": "email", "autofocus": True}
        ),
    )

    def get_users(self, email):
        """Igual que Django, pero filtra por el campo real `activo`.

        El modelo Usuario expone `is_active` como propiedad (no como columna de
        la base de datos), por lo que no se puede filtrar por `is_active` en el
        ORM; la columna real es `activo`.
        """
        Usuario = get_user_model()
        campo_correo = Usuario.get_email_field_name()
        candidatos = Usuario._default_manager.filter(**{f"{campo_correo}__iexact": email, "activo": True})
        return (
            u
            for u in candidatos
            if u.has_usable_password() and _unicode_ci_compare(email, getattr(u, campo_correo))
        )


class EstablecerContrasenaForm(SetPasswordForm):
    """Define la nueva contraseña desde el enlace recibido por correo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Repita la nueva contraseña"
        for nombre in ("new_password1", "new_password2"):
            self.fields[nombre].widget.attrs.update(
                {"class": "form-control form-control-lg", "autocomplete": "new-password"}
            )
