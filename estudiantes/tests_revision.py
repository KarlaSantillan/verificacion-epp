"""Pruebas de HU05: revisión de carnés pendientes (RF04 – CP12 y CP14).

Ejecutar con:  python manage.py test estudiantes
"""
from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from estudiantes.models import CarnetEstudiantil, Estudiante
from estudiantes.servicios import calcular_hash
from estudiantes.sga import DatosSGA
from usuarios.models import Rol, Usuario

CLAVE = "ClaveSegura-2026"
DATOS = {
    "nombres": "maria jose", "apellidos": "perez lopez", "cedula": "",
    "carrera": "Biotecnología", "facultad": "", "modalidad": "", "nivel": "3", "fecha_fin_vigencia": "2026-12-22",
}


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False)
class RevisionPendientesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Ana", apellidos="Prueba", rol=rol)

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)
        self.carnet = self.crear_pendiente("PEND0001")

    def crear_pendiente(self, codigo):
        return CarnetEstudiantil.objects.create(
            usuario_registro=self.docente, estudiante=Estudiante.objects.create(),
            qr_hash=calcular_hash(codigo), codigo_validacion=codigo,
        )

    def url_completar(self, carnet=None):
        return reverse("estudiantes:completar", args=[(carnet or self.carnet).id_carnet])

    # CA01
    def test_ca01_lista_muestra_codigo_y_enlace_al_sga_en_pestana_nueva(self):
        html = self.client.get(reverse("estudiantes:pendientes")).content.decode()
        self.assertIn("PEND0001", html)
        self.assertIn("digital?code=PEND0001", html)
        self.assertIn('target="_blank"', html)

    def test_la_lista_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("estudiantes:pendientes")).status_code, 302)

    # CA02 (CP12)
    def test_cp12_al_guardar_el_carne_queda_registrado_con_nombre(self):
        respuesta = self.client.post(self.url_completar(), DATOS)
        self.assertRedirects(respuesta, reverse("estudiantes:pendientes"))
        self.carnet.refresh_from_db()
        self.assertEqual(self.carnet.estado_registro, CarnetEstudiantil.REGISTRADO)
        self.assertEqual(str(self.carnet.estudiante), "Maria Jose Perez Lopez")
        self.assertEqual(self.carnet.fecha_fin_vigencia, date(2026, 12, 22))
        self.assertIsNotNone(self.carnet.fecha_revision)
        self.assertFalse(CarnetEstudiantil.objects.filter(estado_registro=CarnetEstudiantil.PENDIENTE).exists())

    def test_nombres_obligatorios_y_cedula_con_formato(self):
        respuesta = self.client.post(self.url_completar(), {**DATOS, "nombres": "", "cedula": "12ab"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La cédula debe tener 10 dígitos.")
        self.carnet.refresh_from_db()
        self.assertEqual(self.carnet.estado_registro, CarnetEstudiantil.PENDIENTE)

    # CA03 (CP14)
    def test_cp14_cedula_existente_asocia_el_carne_sin_duplicar(self):
        existente = Estudiante.objects.create(cedula="0912345678", nombres="Maria Jose", apellidos="Perez Lopez")
        vacio_id = self.carnet.estudiante_id
        self.client.post(self.url_completar(), {**DATOS, "cedula": "0912345678"})
        self.carnet.refresh_from_db()
        self.assertEqual(self.carnet.estudiante_id, existente.pk)
        self.assertFalse(Estudiante.objects.filter(pk=vacio_id).exists())
        self.assertEqual(Estudiante.objects.filter(cedula="0912345678").count(), 1)

    def test_un_carne_registrado_ya_no_se_puede_completar(self):
        self.carnet.estado_registro = CarnetEstudiantil.REGISTRADO
        self.carnet.save()
        self.assertEqual(self.client.get(self.url_completar()).status_code, 404)

    # Volver a consultar el SGA
    def reconsultar(self):
        return self.client.post(reverse("estudiantes:reconsultar", args=[self.carnet.id_carnet]))

    @patch("estudiantes.revision._consultar_sga")
    def test_reconsultar_sga_valido_registra_el_carne(self, consultar):
        consultar.return_value = DatosSGA(valido=True, nombres="Luis", apellidos="Mora", carrera="Biotecnología")
        self.reconsultar()
        self.carnet.refresh_from_db()
        self.assertEqual(self.carnet.estado_registro, CarnetEstudiantil.REGISTRADO)
        self.assertEqual(str(self.carnet.estudiante), "Luis Mora")

    @patch("estudiantes.revision._consultar_sga", return_value=None)
    def test_reconsultar_sin_respuesta_mantiene_pendiente(self, consultar):
        self.reconsultar()
        self.carnet.refresh_from_db()
        self.assertEqual(self.carnet.estado_registro, CarnetEstudiantil.PENDIENTE)
