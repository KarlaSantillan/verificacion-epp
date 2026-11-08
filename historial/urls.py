from django.urls import path

from . import views

app_name = "historial"

urlpatterns = [
    path("registros/", views.registros, name="registros"),
    path("incidencias/", views.incidencias, name="incidencias"),
    path("reincidentes/csv/", views.reincidentes_csv, name="reincidentes_csv"),  # HU16
    path("reincidentes/<int:id_estudiante>/", views.historial_estudiante, name="reincidente"),  # HU15
    path("reincidentes/<int:id_estudiante>/llamado/", views.llamado, name="llamado"),  # HU16
    path("validacion/<int:pk>/", views.detalle, name="detalle"),
    path("validacion/<int:pk>/corregir/<int:id_detalle>/", views.corregir, name="corregir"),
]
