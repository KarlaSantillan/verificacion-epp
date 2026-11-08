from django.urls import path

from . import views, views_deteccion, views_evaluacion, views_registro

app_name = "verificacion"

urlpatterns = [
    path("", views.verificar, name="verificar"),
    path("api/identificar/", views.identificar, name="identificar"),
    path("api/detectar/", views_deteccion.detectar, name="detectar"),  # TK07
    path("api/evaluar/", views_evaluacion.evaluar_cumplimiento, name="evaluar"),  # HU07
    path("api/registrar/", views_registro.registrar, name="registrar"),  # HU08
]
