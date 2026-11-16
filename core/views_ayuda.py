from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def ayuda(request):
    """Página de ayuda: guía de uso, preguntas frecuentes y significado de los estados.

    Es solo descriptiva: no consulta ni modifica la base de datos.
    """
    return render(request, "core/ayuda.html")
