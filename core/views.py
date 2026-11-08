from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from configuracion.models import Laboratorio, ModeloVision, PeriodoAcademico

from . import indicadores
from .decorators import solo_administrador


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


@login_required
def inicio(request):
    """Inicio con el dashboard de indicadores (HU14 / RF11). Lo ven el docente y el administrador."""
    hoy = timezone.localdate()
    periodos = list(PeriodoAcademico.objects.order_by("-fecha_inicio"))
    laboratorios = list(Laboratorio.objects.order_by("-activo", "nombre"))
    periodo_vigente = next((p for p in periodos if p.fecha_inicio <= hoy <= p.fecha_fin), None)

    # Filtros (HU14-CA02). Por defecto: el periodo vigente (o el más reciente) y todos los laboratorios.
    id_periodo = _entero(request.GET.get("periodo"))
    periodo = next((p for p in periodos if p.pk == id_periodo), None) or periodo_vigente or (periodos[0] if periodos else None)
    id_laboratorio = _entero(request.GET.get("laboratorio"))
    laboratorio = next((l for l in laboratorios if l.pk == id_laboratorio), None)

    contexto = {
        "periodos": periodos,
        "laboratorios": laboratorios,
        "periodo": periodo,
        "periodo_vigente": periodo_vigente,
        "laboratorio": laboratorio,
        "modelo_activo": ModeloVision.objects.filter(activo=True).first(),
    }
    if periodo is not None:
        consulta = indicadores.validaciones(periodo, laboratorio)
        agrupacion = request.GET.get("agrupar")
        if agrupacion not in ("dia", "semana"):
            agrupacion = indicadores.agrupacion_automatica(consulta)
        puntos = indicadores.serie(consulta, agrupacion)
        mensaje, icono = indicadores.mensaje_resumen(puntos, agrupacion)
        contexto.update({
            "resumen": indicadores.resumen(consulta),
            "faltantes": indicadores.epp_faltantes(consulta),
            "por_laboratorio": indicadores.por_laboratorio(consulta) if laboratorio is None else [],
            "agrupacion": agrupacion,
            "serie": puntos,
            "mensaje_serie": mensaje,
            "icono_serie": icono,
        })
    return render(request, "core/inicio.html", contexto)


@solo_administrador
def administracion(request):
    return render(request, "core/administracion.html")
