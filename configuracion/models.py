from django.core.validators import MaxValueValidator, MinValueValidator
from decimal import Decimal

from django.db import models
from django.db.models import F, Q


class PeriodoAcademico(models.Model):
    """EPP_M_PERIODO_ACADEMICO"""

    id_periodo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=80)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    class Meta:
        db_table = "epp_m_periodo_academico"
        verbose_name = "periodo académico"
        verbose_name_plural = "periodos académicos"
        ordering = ["-fecha_inicio"]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_fin__gt=F("fecha_inicio")), name="ck_periodo_fechas"),
        ]

    def __str__(self):
        return self.nombre


class Laboratorio(models.Model):
    """EPP_M_LABORATORIO"""

    id_laboratorio = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    ubicacion = models.CharField(max_length=120, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    tiempo_estabilizacion_segundos = models.PositiveIntegerField(default=3)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "epp_m_laboratorio"
        verbose_name = "laboratorio"
        verbose_name_plural = "laboratorios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Epp(models.Model):
    """EPP_M_EPP"""

    id_epp = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=80)
    clase_modelo = models.CharField(max_length=80, help_text="Nombre de la clase en el modelo YOLOv8, por ejemplo: gloves.")
    descripcion = models.TextField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "epp_m_epp"
        verbose_name = "EPP"
        verbose_name_plural = "catálogo de EPP"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class LaboratorioEpp(models.Model):
    """EPP_M_LABORATORIO_EPP: requisitos de EPP de cada laboratorio."""

    id_laboratorio_epp = models.AutoField(primary_key=True)
    laboratorio = models.ForeignKey(Laboratorio, on_delete=models.PROTECT, db_column="id_laboratorio", related_name="requisitos")
    epp = models.ForeignKey(Epp, on_delete=models.PROTECT, db_column="id_epp", related_name="requisitos")
    obligatorio = models.BooleanField(default=True)
    confianza_minima = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.80"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
        help_text="Valor entre 0 y 1. Ejemplo: 0.85 equivale a 85 % de confianza.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "epp_m_laboratorio_epp"
        verbose_name = "requisito de EPP"
        verbose_name_plural = "requisitos de EPP por laboratorio"
        constraints = [
            models.UniqueConstraint(fields=["laboratorio", "epp"], name="uq_laboratorio_epp"),
            models.CheckConstraint(condition=Q(confianza_minima__gte=0) & Q(confianza_minima__lte=1), name="ck_confianza_minima_rango"),
        ]

    def __str__(self):
        return f"{self.laboratorio} – {self.epp}"


class ModeloVision(models.Model):
    """EPP_M_MODELO_VISION"""

    id_modelo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=80)
    version = models.CharField(max_length=80)
    dataset_entrenamiento = models.CharField(max_length=200, null=True, blank=True)
    fecha_entrenamiento = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=False)

    class Meta:
        db_table = "epp_m_modelo_vision"
        verbose_name = "modelo de visión"
        verbose_name_plural = "modelos de visión"
        constraints = [
            # Solo puede existir un modelo activo a la vez (RF15-CA03).
            models.UniqueConstraint(fields=["activo"], condition=Q(activo=True), name="uq_un_solo_modelo_activo"),
        ]

    def __str__(self):
        return f"{self.nombre} {self.version}"


class Parametro(models.Model):
    """EPP_M_PARAMETRO: configuración global del sistema."""

    id_parametro = models.AutoField(primary_key=True)
    clave = models.CharField(max_length=50, unique=True)
    valor = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "epp_m_parametro"
        verbose_name = "parámetro"
        verbose_name_plural = "parámetros generales"
        ordering = ["clave"]

    def __str__(self):
        return f"{self.clave} = {self.valor}"

    @classmethod
    def obtener(cls, clave, por_defecto=None):
        try:
            return cls.objects.get(clave=clave).valor
        except cls.DoesNotExist:
            return por_defecto
