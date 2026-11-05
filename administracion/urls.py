from django.urls import path

from . import views

app_name = "administracion"

urlpatterns = [
    path("laboratorios/", views.laboratorios, name="laboratorios"),
    path("laboratorios/nuevo/", views.laboratorio_editar, name="laboratorio_nuevo"),
    path("laboratorios/<int:pk>/", views.laboratorio_editar, name="laboratorio_editar"),
    path("catalogo-epp/", views.catalogo, name="catalogo"),
    path("catalogo-epp/nuevo/", views.epp_editar, name="epp_nuevo"),
    path("catalogo-epp/<int:pk>/", views.epp_editar, name="epp_editar"),
    path("estudiantes/", views.estudiantes, name="estudiantes"),
    path("estudiantes/<int:pk>/", views.estudiante_editar, name="estudiante_editar"),
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/nuevo/", views.usuario_editar, name="usuario_nuevo"),
    path("usuarios/<int:pk>/", views.usuario_editar, name="usuario_editar"),
    path("periodos/", views.periodos, name="periodos"),
    path("periodos/<int:pk>/", views.periodo_editar, name="periodo_editar"),
    path("parametros/", views.parametros, name="parametros"),
    path("parametros/<int:pk>/", views.parametro_editar, name="parametro_editar"),
    path("modelo-vision/", views.modelos, name="modelos"),
    path("modelo-vision/nuevo/", views.modelo_editar, name="modelo_nuevo"),
    path("modelo-vision/<int:pk>/", views.modelo_editar, name="modelo_editar"),
    path("modelo-vision/<int:pk>/activar/", views.modelo_activar, name="modelo_activar"),
    path("<str:tipo>/<int:pk>/activo/", views.cambiar_activo, name="cambiar_activo"),
]
