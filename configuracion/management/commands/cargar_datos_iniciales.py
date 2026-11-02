"""Carga los datos iniciales del sistema. Se puede ejecutar varias veces sin duplicar.

Uso: python manage.py cargar_datos_iniciales
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from configuracion.models import Epp, Laboratorio, LaboratorioEpp, Parametro, PeriodoAcademico
from usuarios.models import Rol

ROLES = [
    (Rol.DOCENTE, "Opera la verificación, consulta registros y corrige detecciones."),
    (Rol.ADMINISTRADOR, "Gestiona usuarios, laboratorios, requisitos de EPP y parámetros."),
]

EPPS = [
    ("Bata", "lab_coat", "Bata de laboratorio de manga larga."),
    ("Guantes", "gloves", "Guantes desechables en ambas manos."),
    ("Gafas de seguridad", "safety_glasses", "Protección ocular frente a salpicaduras."),
    ("Mascarilla", "mask", "Cubre nariz y boca."),
]

# Laboratorio A: los cuatro EPP obligatorios. Laboratorio B: mascarilla no obligatoria.
LABORATORIOS = [
    ("Laboratorio piloto A", 3, {"Bata": True, "Guantes": True, "Gafas de seguridad": True, "Mascarilla": True}, Decimal("0.85")),
    ("Laboratorio piloto B", 2, {"Bata": True, "Guantes": True, "Gafas de seguridad": True, "Mascarilla": False}, Decimal("0.80")),
]

PARAMETROS = [
    ("umbral_incidencias", "3", "Incidencias por periodo a partir de las cuales se requiere llamado de atención."),
    ("prefijo_qr_valido", "https://sga.unemi.edu.ec/p_valida_carnet/", "Inicio obligatorio del contenido del QR del carné."),
]


class Command(BaseCommand):
    help = "Carga roles, catálogo de EPP, laboratorios piloto, periodo académico y parámetros iniciales."

    @transaction.atomic
    def handle(self, *args, **options):
        for nombre, descripcion in ROLES:
            Rol.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})

        epps = {}
        for nombre, clase, descripcion in EPPS:
            epps[nombre], _ = Epp.objects.get_or_create(nombre=nombre, defaults={"clase_modelo": clase, "descripcion": descripcion})

        for nombre, estabilizacion, requisitos, umbral in LABORATORIOS:
            lab, _ = Laboratorio.objects.get_or_create(nombre=nombre, defaults={"tiempo_estabilizacion_segundos": estabilizacion})
            for epp_nombre, obligatorio in requisitos.items():
                LaboratorioEpp.objects.get_or_create(
                    laboratorio=lab, epp=epps[epp_nombre], defaults={"obligatorio": obligatorio, "confianza_minima": umbral}
                )

        PeriodoAcademico.objects.get_or_create(
            nombre="Agosto - Diciembre 2026", defaults={"fecha_inicio": date(2026, 8, 13), "fecha_fin": date(2026, 12, 22)}
        )

        for clave, valor, descripcion in PARAMETROS:
            Parametro.objects.get_or_create(clave=clave, defaults={"valor": valor, "descripcion": descripcion})

        self.stdout.write(self.style.SUCCESS("Datos iniciales cargados correctamente."))
