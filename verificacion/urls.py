from django.urls import path

from . import sesion_practica, views, views_correo, views_deteccion, views_evaluacion, views_registro

app_name = "verificacion"

urlpatterns = [
    path("", views.verificar, name="verificar"),
    path("api/identificar/", views.identificar, name="identificar"),
    path("api/detectar/", views_deteccion.detectar, name="detectar"),  # TK07
    path("api/evaluar/", views_evaluacion.evaluar_cumplimiento, name="evaluar"),  # HU07
    path("api/registrar/", views_registro.registrar, name="registrar"),  # HU08
    path("api/sesion-practica/", sesion_practica.guardar, name="sesion_practica"),
    path("api/correo-estudiante/", views_correo.guardar_correo, name="correo_estudiante"),  # HU16: notificación
]
