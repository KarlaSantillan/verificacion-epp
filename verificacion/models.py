from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from configuracion.models import Epp, Laboratorio, ModeloVision, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil


class Validacion(models.Model):
    """EPP_T_VALIDACION. El estudiante se obtiene a través del carné."""

    CONFORME = "conforme"
    NO_CONFORME = "no_conforme"
    RESULTADOS = [(CONFORME, "Cumple"), (NO_CONFORME, "No cumple")]

    id_validacion = models.AutoField(primary_key=True)
    usuario_supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="id_usuario_supervisor", related_name="validaciones_supervisadas"
    )
    periodo = models.ForeignKey(PeriodoAcademico, on_delete=models.PROTECT, db_column="id_periodo", related_name="validaciones")
    modelo = models.ForeignKey(ModeloVision, on_delete=models.PROTECT, db_column="id_modelo", related_name="validaciones")
    carnet = models.ForeignKey(CarnetEstudiantil, on_delete=models.PROTECT, db_column="id_carnet", related_name="validaciones")
    laboratorio = models.ForeignKey(Laboratorio, on_delete=models.PROTECT, db_column="id_laboratorio", related_name="validaciones")
    fecha_hora = models.DateTimeField(default=timezone.now)
    resultado_modelo = models.CharField(max_length=12, choices=RESULTADOS)
    resultado_final = models.CharField(max_length=12, choices=RESULTADOS)
    corregida = models.BooleanField(default=False)
    observacion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "epp_t_validacion"
        verbose_name = "validación"
        verbose_name_plural = "validaciones"
        ordering = ["-fecha_hora"]

    @property
    def estudiante(self):
        return self.carnet.estudiante

    def __str__(self):
        return f"Validación {self.id_validacion} – {self.get_resultado_final_display()}"


class ValidacionDetalle(models.Model):
    """EPP_T_VALIDACION_DETALLE: resultado por cada EPP configurado."""

    id_detalle = models.AutoField(primary_key=True)
    validacion = models.ForeignKey(Validacion, on_delete=models.PROTECT, db_column="id_validacion", related_name="detalles")
    epp = models.ForeignKey(Epp, on_delete=models.PROTECT, db_column="id_epp", related_name="detalles")
    requerido = models.BooleanField()
    detectado_modelo = models.BooleanField()
    detectado_final = models.BooleanField()
    confianza = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    umbral_usado = models.DecimalField(max_digits=5, decimal_places=4)

    class Meta:
        db_table = "epp_t_validacion_detalle"
        verbose_name = "detalle de validación"
        verbose_name_plural = "detalles de validación"
        constraints = [
            models.UniqueConstraint(fields=["validacion", "epp"], name="uq_detalle_validacion_epp"),
            models.CheckConstraint(
                condition=Q(confianza__isnull=True) | (Q(confianza__gte=0) & Q(confianza__lte=1)), name="ck_detalle_confianza_rango"
            ),
        ]

    def __str__(self):
        return f"{self.validacion_id} – {self.epp}"


class CorreccionValidacion(models.Model):
    """EPP_P_CORRECCION_VALIDACION. La validación se obtiene a través del detalle."""

    FALSO_POSITIVO = "falso_positivo"
    FALSO_NEGATIVO = "falso_negativo"
    TIPOS_ERROR = [(FALSO_POSITIVO, "Falso positivo"), (FALSO_NEGATIVO, "Falso negativo")]

    id_correccion = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="id_usuario", related_name="correcciones")
    detalle = models.ForeignKey(ValidacionDetalle, on_delete=models.PROTECT, db_column="id_detalle", related_name="correcciones")
    tipo_error = models.CharField(max_length=20, choices=TIPOS_ERROR)
    valor_anterior = models.BooleanField()
    valor_nuevo = models.BooleanField()
    observacion = models.TextField()
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "epp_p_correccion_validacion"
        verbose_name = "corrección"
        verbose_name_plural = "correcciones"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_tipo_error_display()} – detalle {self.detalle_id}"
