"""Sección «Prácticas»: resúmenes de las prácticas anteriores (pedido en la tutoría).

No usa tablas nuevas: las prácticas se arman a partir de las validaciones guardadas
(docente, materia y práctica, fecha y pausas de más de 2 horas). Ver verificacion/resumen_practica.py.
"""
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from usuarios.models import Usuario
from verificacion import resumen_practica


@login_required
def practicas(request):
    hoy = timezone.localdate()
    desde = parse_date(request.GET.get("desde", "")) or hoy - timedelta(days=30)
    hasta = parse_date(request.GET.get("hasta", "")) or hoy
    materia = request.GET.get("materia", "").strip()
    es_admin = request.user.es_administrador
    # El docente ve solo sus prácticas; el administrador, las de todos o las de un docente.
    docente = request.user
    id_docente = request.GET.get("docente", "")
    if es_admin:
        docente = Usuario.objects.filter(pk=int(id_docente)).first() if id_docente.isdigit() else None

    lista = resumen_practica.practicas(desde, hasta, usuario=docente, materia=materia)
    for r in lista:
        r.consulta = urlencode({
            "docente": r.usuario_id, "desde": r.inicio.isoformat(), "hasta": r.fin.isoformat(),
            "materia": r.materia, "practica": r.practica,
        })
    pagina = Paginator(lista, 15).get_page(request.GET.get("pagina"))
    filtros = {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "materia": materia, "docente": id_docente if es_admin else ""}
    contexto = {
        "pagina": pagina,
        "filtros": filtros,
        "parametros_url": urlencode({k: v for k, v in filtros.items() if v}),
        "docentes": Usuario.objects.filter(validaciones_supervisadas__isnull=False).distinct().order_by("apellidos") if es_admin else [],
    }
    return render(request, "historial/practicas.html", contexto)
