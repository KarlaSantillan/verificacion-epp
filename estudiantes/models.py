from django.conf import settings
from django.db import models


class Estudiante(models.Model):
    """EPP_M_ESTUDIANTE. Los datos personales son opcionales: un carné nuevo
    crea un estudiante vacío que se completa después (RF04)."""

    id_estudiante = models.AutoField(primary_key=True)
    cedula = models.CharField(max_length=15, unique=True, null=True, blank=True)
    nombres = models.CharField(max_length=120, null=True, blank=True)
    apellidos = models.CharField(max_length=120, null=True, blank=True)
    carrera = models.CharField(max_length=120, null=True, blank=True)
    facultad = models.CharField(max_length=120, null=True, blank=True)
    modalidad = models.CharField(max_length=30, null=True, blank=True)
    nivel = models.CharField(max_length=50, null=True, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "epp_m_estudiante"
        verbose_name = "estudiante"
        verbose_name_plural = "estudiantes"
        ordering = ["apellidos", "nombres"]

    def save(self, *args, **kwargs):
        # Una cédula vacía se guarda como NULL para no romper la restricción UNIQUE.
        if not self.cedula:
            self.cedula = None
        super().save(*args, **kwargs)

    def __str__(self):
        if self.nombres or self.apellidos:
            return f"{self.nombres or ''} {self.apellidos or ''}".strip()
        return f"Estudiante pendiente #{self.id_estudiante}"


class CarnetEstudiantil(models.Model):
    """EPP_M_CARNET_ESTUDIANTIL"""

    PENDIENTE = "pendiente"
    REGISTRADO = "registrado"
    ESTADOS = [(PENDIENTE, "Pendiente de revisión"), (REGISTRADO, "Registrado")]

    id_carnet = models.AutoField(primary_key=True)
    usuario_registro = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="id_usuario_registro", related_name="carnets_registrados"
    )
    estudiante = models.ForeignKey(Estudiante, on_delete=models.PROTECT, db_column="id_estudiante", related_name="carnets")
    qr_hash = models.CharField(max_length=64, unique=True, help_text="HMAC-SHA256 del código de validación.")
    codigo_validacion = models.CharField(max_length=50, unique=True, null=True, blank=True)
    fecha_inicio_vigencia = models.DateField(null=True, blank=True)
    fecha_fin_vigencia = models.DateField(null=True, blank=True)
    estado_registro = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "epp_m_carnet_estudiantil"
        verbose_name = "carné estudiantil"
        verbose_name_plural = "carnés estudiantiles"
        ordering = ["-fecha_creacion"]

    def save(self, *args, **kwargs):
        if not self.codigo_validacion:
            self.codigo_validacion = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Carné {self.codigo_validacion or self.id_carnet} – {self.estudiante}"
