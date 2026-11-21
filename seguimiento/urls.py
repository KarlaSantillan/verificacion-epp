from django.urls import path

from . import views

app_name = "seguimiento"

urlpatterns = [
    path("api/notificaciones/", views.notificaciones, name="notificaciones"),  # campana que se actualiza sola
]
