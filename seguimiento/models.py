from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from configuracion.models import PeriodoAcademico
from estudiantes.models import Estudiante


class LlamadoAtencion(models.Model):
    """EPP_T_LLAMADO_ATENCION"""

    id_llamado = models.AutoField(primary_key=True)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.PROTECT, db_column="id_estudiante", related_name="llamados")
    periodo = models.ForeignKey(PeriodoAcademico, on_delete=models.PROTECT, db_column="id_periodo", related_name="llamados")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="id_usuario", related_name="llamados_registrados")
    cantidad_incidencias = models.PositiveIntegerField()
    observacion = models.TextField()
    fecha_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "epp_t_llamado_atencion"
        verbose_name = "llamado de atención"
        verbose_name_plural = "llamados de atención"
        ordering = ["-fecha_hora"]
        constraints = [
            models.CheckConstraint(condition=Q(cantidad_incidencias__gt=0), name="ck_llamado_cantidad_positiva"),
        ]

    def __str__(self):
        return f"Llamado a {self.estudiante} ({self.fecha_hora:%d/%m/%Y})"
