from django.urls import path

from . import views
from .views_ayuda import ayuda

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("administracion/", views.administracion, name="administracion"),
    path("ayuda/", ayuda, name="ayuda"),
]
