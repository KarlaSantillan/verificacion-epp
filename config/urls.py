from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuenta/", include("usuarios.urls")),
    path("verificacion/", include("verificacion.urls")),
    path("estudiantes/", include("estudiantes.urls")),
    path("gestion/", include("administracion.urls")),
    path("", include("core.urls")),
]

