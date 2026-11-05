from django.urls import path

from . import views

app_name = "estudiantes"

urlpatterns = [
    path("pendientes/", views.pendientes, name="pendientes"),
    path("pendientes/<int:id_carnet>/completar/", views.completar, name="completar"),
    path("pendientes/<int:id_carnet>/consultar-sga/", views.reconsultar, name="reconsultar"),
]
