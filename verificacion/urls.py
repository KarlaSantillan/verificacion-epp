from django.urls import path

from . import views, views_deteccion, views_evaluacion

app_name = "verificacion"

urlpatterns = [
    path("", views.verificar, name="verificar"),
    path("api/identificar/", views.identificar, name="identificar"),
    path("api/detectar/", views_deteccion.detectar, name="detectar"),  # TK07
    path("api/evaluar/", views_evaluacion.evaluar_cumplimiento, name="evaluar"),  # HU07
]
