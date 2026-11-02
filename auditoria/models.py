from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Auditoria(models.Model):
    """EPP_T_AUDITORIA: bitácora de solo lectura."""

    USUARIO = "usuario"
    SISTEMA = "sistema"
    TIPOS_ACTOR = [(USUARIO, "Usuario"), (SISTEMA, "Sistema")]
    ACCIONES = [("INSERT", "Inserción"), ("UPDATE", "Modificación"), ("DELETE", "Desactivación"), ("LOGIN", "Inicio de sesión")]

    id_auditoria = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="id_usuario", null=True, blank=True, related_name="eventos_auditoria"
    )
    tipo_actor = models.CharField(max_length=15, choices=TIPOS_ACTOR)
    tabla_afectada = models.CharField(max_length=80)
    id_registro_afectado = models.IntegerField(null=True, blank=True)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    datos_anteriores = models.JSONField(null=True, blank=True)
    datos_nuevos = models.JSONField(null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    fecha_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "epp_t_auditoria"
        verbose_name = "evento de auditoría"
        verbose_name_plural = "auditoría"
        ordering = ["-fecha_hora"]
        constraints = [
            # Un evento de tipo "usuario" siempre debe indicar el usuario.
            models.CheckConstraint(condition=Q(tipo_actor="sistema") | Q(usuario__isnull=False), name="ck_auditoria_actor_usuario"),
        ]

    def __str__(self):
        return f"{self.accion} {self.tabla_afectada} ({self.fecha_hora:%d/%m/%Y %H:%M})"
