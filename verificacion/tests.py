"""Pruebas de HU03: ingreso manual del código del carné (RF03, CP09 y CP10).

Ejecutar con:  python manage.py test verificacion
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from estudiantes.models import CarnetEstudiantil
from usuarios.models import Rol, Usuario

CODIGO = "TEST0001"
QR = f"https://sga.unemi.edu.ec/p_valida_carnet/digital?code={CODIGO}"
CLAVE = "ClaveSegura-2026"


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False)
class IngresoManualTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Ana", apellidos="Prueba", rol=rol)

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def enviar(self, datos):
        return self.client.post(reverse("verificacion:identificar"), json.dumps(datos), content_type="application/json")

    def test_cp09_el_codigo_identifica_al_mismo_carne_que_el_qr(self):
        """CA01: el código escrito encuentra el mismo carné que su QR."""
        por_qr = self.enviar({"qr": QR}).json()
        por_codigo = self.enviar({"codigo": CODIGO}).json()
        self.assertEqual(por_codigo["carnet"]["id"], por_qr["carnet"]["id"])
        self.assertEqual(CarnetEstudiantil.objects.count(), 1)

    def test_el_codigo_con_espacios_se_acepta(self):
        self.enviar({"qr": QR})
        respuesta = self.enviar({"codigo": "  TEST 0001 "})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(CarnetEstudiantil.objects.count(), 1)

    def test_cp10_codigo_vacio_se_rechaza_con_mensaje(self):
        """CA02: código vacío."""
        respuesta = self.enviar({"codigo": "   "})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["estado"], "codigo_no_valido")
        self.assertIn("Escriba el código", respuesta.json()["mensaje"])

    def test_cp10_codigo_con_caracteres_no_validos_se_rechaza(self):
        """CA02: formato no válido."""
        respuesta = self.enviar({"codigo": "12345-<script>"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["estado"], "codigo_no_valido")
        self.assertEqual(CarnetEstudiantil.objects.count(), 0)

    def test_codigo_no_registrado_crea_carne_nuevo(self):
        """RF03-CA03: un código nuevo sigue el registro de carné nuevo (RF04)."""
        respuesta = self.enviar({"codigo": "NUEVO123"})
        self.assertEqual(respuesta.json()["estado"], "nuevo")
        self.assertEqual(CarnetEstudiantil.objects.count(), 1)
