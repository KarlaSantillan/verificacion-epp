from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from configuracion.models import Epp, Laboratorio, ModeloVision, PeriodoAcademico

from .decorators import solo_administrador


@login_required
def inicio(request):
    hoy = timezone.localdate()
    contexto = {
        "laboratorios_activos": Laboratorio.objects.filter(activo=True).count(),
        "epp_activos": Epp.objects.filter(activo=True).count(),
        "periodo_actual": PeriodoAcademico.objects.filter(fecha_inicio__lte=hoy, fecha_fin__gte=hoy).first(),
        "modelo_activo": ModeloVision.objects.filter(activo=True).first(),
    }
    return render(request, "core/inicio.html", contexto)


@solo_administrador
def administracion(request):
    return render(request, "core/administracion.html")
