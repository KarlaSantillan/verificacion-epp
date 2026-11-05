"""Pruebas de HU07: resultado de cumplimiento (RF06 – CP18 a CP21).

La estabilización en la pantalla (CP22) se prueba de forma manual.
Ejecutar con:  python manage.py test verificacion
"""
import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from configuracion.models import Epp, Laboratorio, LaboratorioEpp
from usuarios.models import Rol, Usuario
from verificacion.evaluacion import SinRequisitos, evaluar

CLAVE = "ClaveSegura-2026"
TODOS = {"lab_coat": 0.90, "gloves": 0.90, "safety_glasses": 0.90, "mask": 0.90}


class EvaluacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Ana", apellidos="Prueba", rol=rol)
        epps = {
            clase: Epp.objects.create(nombre=nombre, clase_modelo=clase)
            for clase, nombre in [("lab_coat", "Bata"), ("gloves", "Guantes"), ("safety_glasses", "Gafas de seguridad"), ("mask", "Mascarilla")]
        }
        # Laboratorio A: los 4 obligatorios con 0.85. Laboratorio B: mascarilla opcional con 0.80.
        cls.lab_a = Laboratorio.objects.create(nombre="Lab A", tiempo_estabilizacion_segundos=3)
        cls.lab_b = Laboratorio.objects.create(nombre="Lab B", tiempo_estabilizacion_segundos=2)
        for epp in epps.values():
            LaboratorioEpp.objects.create(laboratorio=cls.lab_a, epp=epp, confianza_minima=Decimal("0.85"))
            LaboratorioEpp.objects.create(
                laboratorio=cls.lab_b, epp=epp, confianza_minima=Decimal("0.80"), obligatorio=epp.clase_modelo != "mask"
            )
        cls.lab_vacio = Laboratorio.objects.create(nombre="Lab sin EPP")

    # --- Regla (servicio)
    def test_cp18_con_todos_los_epp_cumple(self):
        self.assertTrue(evaluar(self.lab_a, TODOS).cumple)

    def test_cp19_sin_gafas_no_cumple_y_las_nombra(self):
        resultado = evaluar(self.lab_a, {**TODOS, "safety_glasses": None})
        self.assertFalse(resultado.cumple)
        self.assertEqual(resultado.faltantes, ["Gafas de seguridad"])

    def test_cp20_mismo_estudiante_distinto_resultado_por_laboratorio(self):
        sin_mascarilla = {k: v for k, v in TODOS.items() if k != "mask"}
        self.assertFalse(evaluar(self.lab_a, sin_mascarilla).cumple)
        self.assertTrue(evaluar(self.lab_b, sin_mascarilla).cumple)

    def test_ca04_epp_opcional_se_informa_pero_no_cambia_el_resultado(self):
        resultado = evaluar(self.lab_b, {k: v for k, v in TODOS.items() if k != "mask"})
        mascarilla = next(d for d in resultado.detalles if d.clase == "mask")
        self.assertFalse(mascarilla.requerido)
        self.assertFalse(mascarilla.detectado)
        self.assertEqual(resultado.faltantes, [])

    def test_cp21_confianza_bajo_el_umbral_no_cuenta(self):
        resultado = evaluar(self.lab_a, {**TODOS, "gloves": 0.80})
        self.assertFalse(resultado.cumple)
        self.assertEqual(resultado.faltantes, ["Guantes"])

    def test_confianza_igual_al_umbral_si_cuenta(self):
        self.assertTrue(evaluar(self.lab_a, {**TODOS, "gloves": 0.85}).cumple)

    def test_confianza_no_valida_se_ignora(self):
        self.assertFalse(evaluar(self.lab_a, {**TODOS, "mask": 7}).cumple)
        self.assertFalse(evaluar(self.lab_a, {**TODOS, "mask": "abc"}).cumple)

    def test_laboratorio_sin_obligatorios_da_error(self):
        with self.assertRaises(SinRequisitos):
            evaluar(self.lab_vacio, TODOS)

    # --- API
    def api(self, datos):
        return self.client.post(reverse("verificacion:evaluar"), json.dumps(datos), content_type="application/json")

    def test_api_devuelve_resultado_y_detalle(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)
        datos = self.api({"laboratorio": self.lab_a.pk, "confianzas": {**TODOS, "mask": 0.5}}).json()
        self.assertEqual(datos["etiqueta"], "No cumple")
        self.assertEqual(datos["faltantes"], ["Mascarilla"])
        self.assertEqual(len(datos["detalles"]), 4)
        self.assertEqual(set(datos["detalles"][0]), {"epp", "clase", "requerido", "confianza", "umbral", "detectado"})

    def test_api_laboratorio_inactivo(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)
        self.lab_b.activo = False
        self.lab_b.save()
        self.assertEqual(self.api({"laboratorio": self.lab_b.pk, "confianzas": TODOS}).status_code, 400)

    def test_api_requiere_sesion(self):
        self.assertEqual(self.api({"laboratorio": self.lab_a.pk, "confianzas": TODOS}).status_code, 302)
