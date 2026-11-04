from django.urls import path

from . import views

app_name = "verificacion"

urlpatterns = [
    path("", views.verificar, name="verificar"),
    path("api/identificar/", views.identificar, name="identificar"),
]
