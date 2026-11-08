from django.urls import path

from . import views

app_name = "historial"

urlpatterns = [
    path("registros/", views.registros, name="registros"),
    path("incidencias/", views.incidencias, name="incidencias"),
    path("validacion/<int:pk>/", views.detalle, name="detalle"),
    path("validacion/<int:pk>/corregir/<int:id_detalle>/", views.corregir, name="corregir"),
]
