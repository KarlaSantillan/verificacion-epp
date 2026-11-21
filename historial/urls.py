from django.urls import path

from . import views, views_exportacion, views_practica

app_name = "historial"

urlpatterns = [
    path("registros/", views.registros, name="registros"),
    path("incidencias/", views.incidencias, name="incidencias"),
    path("registros/csv/", views_exportacion.registros_csv, name="registros_csv"),  # HU11
    path("incidencias/csv/", views_exportacion.incidencias_csv, name="incidencias_csv"),  # HU11
    path("reincidentes/csv/", views.reincidentes_csv, name="reincidentes_csv"),  # HU16
    path("reincidentes/<int:id_estudiante>/", views.historial_estudiante, name="reincidente"),  # HU15
    path("reincidentes/<int:id_estudiante>/llamado/", views.llamado, name="llamado"),  # HU16
    path("llamados/<int:id_llamado>/notificar/", views.reenviar_notificacion, name="reenviar_notificacion"),  # HU16 / RNF10
    path("validacion/<int:pk>/", views.detalle, name="detalle"),
    path("validacion/<int:pk>/corregir/<int:id_detalle>/", views.corregir, name="corregir"),
    path("validacion/<int:pk>/practica/", views_practica.editar_practica, name="editar_practica"),
]
