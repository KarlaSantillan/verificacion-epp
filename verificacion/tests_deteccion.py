"""Pruebas de TK07: servicio de detección (sin cargar el modelo real).

Ejecutar con:  python manage.py test verificacion
"""
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from verificacion import deteccion
from usuarios.models import Rol, Usuario

CLAVE = "ClaveSegura-2026"
RESPUESTA = {
    "detecciones": [{"clase": "gloves", "confianza": 0.91, "caja": [0.1, 0.2, 0.3, 0.4]}],
    "ms": 80,
    "modelo": "epp-yolov8n v1",
}


class ServicioDeteccionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Ana", apellidos="Prueba", rol=rol)

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def enviar(self, contenido=b"jpeg-falso"):
        archivo = SimpleUploadedFile("f.jpg", contenido, content_type="image/jpeg")
        return self.client.post(reverse("verificacion:detectar"), {"fotograma": archivo})

    @patch("verificacion.deteccion.detectar", return_value=RESPUESTA)
    def test_ca02_respuesta_con_clase_confianza_y_posicion(self, _):
        datos = self.enviar().json()
        self.assertTrue(datos["ok"])
        deteccion_ = datos["detecciones"][0]
        self.assertEqual(set(deteccion_), {"clase", "confianza", "caja"})
        self.assertEqual(len(deteccion_["caja"]), 4)

    @patch("verificacion.deteccion.detectar", side_effect=deteccion.DeteccionNoDisponible("No hay un modelo de visión activo."))
    def test_ca04_servicio_no_disponible_devuelve_error_controlado(self, _):
        respuesta = self.enviar()
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json()["estado"], "servicio_no_disponible")

    @patch("verificacion.deteccion.detectar", side_effect=RuntimeError("falla interna"))
    def test_ca04_falla_inesperada_tambien_es_controlada(self, _):
        with self.assertLogs("verificacion.views_deteccion", level="ERROR"):
            respuesta = self.enviar()
        self.assertEqual(respuesta.status_code, 503)

    def test_sin_modelo_activo_responde_503(self):
        self.assertEqual(self.enviar().status_code, 503)

    def test_sin_fotograma_responde_400(self):
        respuesta = self.client.post(reverse("verificacion:detectar"))
        self.assertEqual(respuesta.status_code, 400)

    def test_imagen_no_valida(self):
        with self.assertRaises(deteccion.ImagenNoValida):
            deteccion.decodificar(b"esto no es una imagen")

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.enviar().status_code, 302)
