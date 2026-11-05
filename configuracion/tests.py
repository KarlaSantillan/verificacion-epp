"""Pruebas de HU12 – Requisitos de EPP por laboratorio.
Ejecutar con:  python manage.py test configuracion
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from configuracion.models import Epp, Laboratorio, LaboratorioEpp


class RequisitosPorLaboratorioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.epps = [Epp.objects.create(nombre=n, clase_modelo=c) for n, c in
                    [("Bata", "lab_coat"), ("Guantes", "gloves"), ("Gafas", "safety_glasses"), ("Mascarilla", "mask")]]
        cls.lab_a = Laboratorio.objects.create(nombre="Lab A")
        cls.lab_b = Laboratorio.objects.create(nombre="Lab B")
        for epp in cls.epps:
            LaboratorioEpp.objects.create(laboratorio=cls.lab_a, epp=epp, obligatorio=True)
            LaboratorioEpp.objects.create(laboratorio=cls.lab_b, epp=epp, obligatorio=epp.nombre != "Mascarilla")

    def obligatorios(self, lab):
        return lab.requisitos.filter(obligatorio=True, activo=True).count()

    def test_ca01_cada_laboratorio_tiene_sus_propios_epp_obligatorios(self):
        self.assertEqual(self.obligatorios(self.lab_a), 4)
        self.assertEqual(self.obligatorios(self.lab_b), 3)

    def test_ca02_cp43_confianza_fuera_de_rango_se_rechaza(self):
        requisito = self.lab_a.requisitos.first()
        requisito.confianza_minima = Decimal("1.5")
        with self.assertRaises(ValidationError):
            requisito.full_clean()

    def test_ca02_confianza_dentro_de_rango_se_acepta(self):
        requisito = self.lab_a.requisitos.first()
        requisito.confianza_minima = Decimal("0.85")
        requisito.full_clean()  # no debe lanzar error

    def test_no_se_repite_un_epp_en_el_mismo_laboratorio(self):
        duplicado = LaboratorioEpp(laboratorio=self.lab_a, epp=self.epps[0])
        with self.assertRaises(ValidationError):
            duplicado.full_clean()