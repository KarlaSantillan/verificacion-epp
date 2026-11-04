"""Pruebas de HU02 (identificación por QR) y HU04 (registro de carné nuevo).

Ejecutar con:  python manage.py test estudiantes
"""
import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from estudiantes.models import CarnetEstudiantil
from estudiantes.servicios import QRNoValido, calcular_hash, extraer_codigo, identificar_por_qr
from usuarios.models import Rol, Usuario

QR_VALIDO = "https://sga.unemi.edu.ec/p_valida_carnet/digital?code=TEST0001"
CLAVE = "ClaveSegura-2026"


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False)
class IdentificacionQRTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Ana", apellidos="Prueba", rol=rol)

    # --- Lógica (servicios) ---
    def test_extrae_el_codigo_de_un_qr_valido(self):
        self.assertEqual(extraer_codigo(QR_VALIDO), "TEST0001")

    def test_cp06_qr_ajeno_a_la_unemi_se_rechaza(self):
        with self.assertRaises(QRNoValido):
            extraer_codigo("https://www.google.com/?code=TEST0001")

    def test_qr_sin_codigo_se_rechaza(self):
        with self.assertRaises(QRNoValido):
            extraer_codigo("https://sga.unemi.edu.ec/p_valida_carnet/digital")

    def test_cp08_el_hash_tiene_64_caracteres_y_no_contiene_el_codigo(self):
        valor = calcular_hash("TEST0001")
        self.assertEqual(len(valor), 64)
        self.assertNotIn("TEST0001", valor)
        self.assertEqual(valor, calcular_hash("TEST0001"))  # siempre el mismo resultado

    def test_cp11_carne_nuevo_se_crea_pendiente_y_con_el_docente(self):
        resultado = identificar_por_qr(QR_VALIDO, self.docente)
        self.assertEqual(resultado.estado, "nuevo")
        self.assertTrue(resultado.permite_verificar)
        self.assertEqual(resultado.carnet.estado_registro, CarnetEstudiantil.PENDIENTE)
        self.assertEqual(resultado.carnet.usuario_registro, self.docente)

    def test_cp13_el_mismo_qr_no_crea_dos_carnes(self):
        primero = identificar_por_qr(QR_VALIDO, self.docente)
        segundo = identificar_por_qr(QR_VALIDO, self.docente)
        self.assertEqual(CarnetEstudiantil.objects.count(), 1)
        self.assertEqual(primero.carnet.pk, segundo.carnet.pk)
        self.assertEqual(segundo.estado, "pendiente")

    def test_carne_registrado_y_vigente_permite_verificar(self):
        carnet = identificar_por_qr(QR_VALIDO, self.docente).carnet
        carnet.estado_registro = CarnetEstudiantil.REGISTRADO
        carnet.fecha_fin_vigencia = timezone.localdate() + timedelta(days=30)
        carnet.save()
        self.assertEqual(identificar_por_qr(QR_VALIDO, self.docente).estado, "registrado")

    def test_cp07_carne_vencido_no_permite_verificar(self):
        carnet = identificar_por_qr(QR_VALIDO, self.docente).carnet
        carnet.estado_registro = CarnetEstudiantil.REGISTRADO
        carnet.fecha_fin_vigencia = timezone.localdate() - timedelta(days=1)
        carnet.save()
        resultado = identificar_por_qr(QR_VALIDO, self.docente)
        self.assertEqual(resultado.estado, "vencido")
        self.assertFalse(resultado.permite_verificar)

    def test_carne_inactivo_no_permite_verificar(self):
        carnet = identificar_por_qr(QR_VALIDO, self.docente).carnet
        carnet.activo = False
        carnet.save()
        self.assertEqual(identificar_por_qr(QR_VALIDO, self.docente).estado, "inactivo")

    # --- Pantalla y API ---
    def api(self, texto):
        return self.client.post(reverse("verificacion:identificar"), json.dumps({"qr": texto}), content_type="application/json")

    def test_api_identifica_un_carne(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)
        respuesta = self.api(QR_VALIDO)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "nuevo")

    def test_api_rechaza_un_qr_no_valido(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)
        respuesta = self.api("hola mundo")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["estado"], "qr_no_valido")

    def test_la_pantalla_requiere_sesion(self):
        self.assertEqual(self.client.get(reverse("verificacion:verificar")).status_code, 302)
