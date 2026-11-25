from email.utils import formataddr

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import EstablecerContrasenaForm, LoginForm, RecuperarContrasenaForm

app_name = "usuarios"

# Remitente de los correos de recuperación: el mismo del resto del sistema (HU16).
_REMITENTE = formataddr((settings.CORREO_NOMBRE, settings.CORREO_REMITENTE))

urlpatterns = [
    path(
        "ingresar/",
        auth_views.LoginView.as_view(
            template_name="usuarios/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),

    # Recuperación de contraseña por correo (administrador y docente).
    # No requiere cambios en la base de datos: usa el correo y el hash ya existentes.
    path(
        "recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="usuarios/password_reset_form.html",
            email_template_name="correo/password_reset_email.txt",
            html_email_template_name="correo/password_reset_email.html",
            subject_template_name="usuarios/password_reset_subject.txt",
            form_class=RecuperarContrasenaForm,
            from_email=_REMITENTE,
            success_url=reverse_lazy("usuarios:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="usuarios/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "recuperar/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="usuarios/password_reset_confirm.html",
            form_class=EstablecerContrasenaForm,
            success_url=reverse_lazy("usuarios:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "recuperar/listo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="usuarios/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
