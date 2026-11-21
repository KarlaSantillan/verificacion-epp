from django.urls import path

from . import sesion_practica, views, views_correo, views_deteccion, views_evaluacion, views_registro, views_resumen

app_name = "verificacion"

urlpatterns = [
    path("", views.verificar, name="verificar"),
    path("api/identificar/", views.identificar, name="identificar"),
    path("api/detectar/", views_deteccion.detectar, name="detectar"),  # TK07
    path("api/evaluar/", views_evaluacion.evaluar_cumplimiento, name="evaluar"),  # HU07
    path("api/registrar/", views_registro.registrar, name="registrar"),  # HU08
    path("api/sesion-practica/", sesion_practica.guardar, name="sesion_practica"),
    path("api/correo-estudiante/", views_correo.guardar_correo, name="correo_estudiante"),  # HU16: notificación
    path("api/resumen-practica/", views_resumen.ver, name="resumen_practica"),  # resumen al cambiar de práctica
    path("api/resumen-practica/enviar/", views_resumen.enviar, name="resumen_practica_enviar"),
    path("resumen-practica/imprimir/", views_resumen.imprimir, name="resumen_practica_imprimir"),
]
