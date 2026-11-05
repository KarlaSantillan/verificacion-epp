from django.urls import path

from . import views, views_deteccion

app_name = "verificacion"

urlpatterns = [
    path("", views.verificar, name="verificar"),
    path("api/identificar/", views.identificar, name="identificar"),
    path("api/detectar/", views_deteccion.detectar, name="detectar"),  # TK07
]
