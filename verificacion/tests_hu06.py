"""Pruebas de HU06: datos que necesita la pantalla de detección en vivo.

El dibujo de los recuadros y el estado en vivo se prueban de forma manual (CP15 a CP17).
Ejecutar con:  python manage.py test verificacion
"""
import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from configuracion.models import Epp, Laboratorio, LaboratorioEpp, ModeloVision
from usuarios.models import Rol, Usuario
from verificacion.views import configuracion_laboratorios

CLAVE = "ClaveSegura-2026"


class PantallaDeteccionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Ana", apellidos="Prueba", rol=rol)
        cls.bata = Epp.objects.create(nombre="Bata", clase_modelo="lab_coat")
        cls.guantes = Epp.objects.create(nombre="Guantes", clase_modelo="gloves")
        cls.lab = Laboratorio.objects.create(nombre="Lab piloto A", tiempo_estabilizacion_segundos=3)
        LaboratorioEpp.objects.create(laboratorio=cls.lab, epp=cls.bata, confianza_minima=Decimal("0.60"))
        LaboratorioEpp.objects.create(laboratorio=cls.lab, epp=cls.guantes, activo=False)
        Laboratorio.objects.create(nombre="Lab cerrado", activo=False)

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def test_solo_laboratorios_y_requisitos_activos(self):
        datos = configuracion_laboratorios()
        self.assertEqual([l["nombre"] for l in datos], ["Lab piloto A"])
        self.assertEqual(datos[0]["estabilizacion"], 3)
        self.assertEqual(datos[0]["requisitos"], [
            {"epp": "Bata", "clase": "lab_coat", "obligatorio": True, "confianza_minima": 0.6},
        ])

    def test_la_pantalla_entrega_los_requisitos_al_navegador(self):
        respuesta = self.client.get(reverse("verificacion:verificar"))
        self.assertContains(respuesta, 'id="datos-laboratorios"')
        self.assertEqual(respuesta.context["nombres_epp"], {"lab_coat": "Bata", "gloves": "Guantes"})
        self.assertContains(respuesta, reverse("verificacion:detectar"))

    def test_aviso_si_no_hay_modelo_activo(self):
        self.assertContains(self.client.get(reverse("verificacion:verificar")), "No hay un modelo de visión activo")
        ModeloVision.objects.create(nombre="epp-yolov8", version="v1", activo=True)
        self.assertNotContains(self.client.get(reverse("verificacion:verificar")), "No hay un modelo de visión activo")
