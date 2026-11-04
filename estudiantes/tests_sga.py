"""Pruebas de la consulta de datos del carné en el SGA.

No se conectan a internet: la respuesta del SGA se simula.
Ejecutar con:  python manage.py test estudiantes
"""
from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from estudiantes import sga
from estudiantes.models import CarnetEstudiantil
from estudiantes.servicios import identificar_por_qr
from usuarios.models import Rol, Usuario

QR = "https://sga.unemi.edu.ec/p_valida_carnet/digital?code=TEST0002"

HTML_VALIDO = """<html><body>
<h2>Carné válido</h2><p>Vigente hasta el 22 de diciembre de 2026</p>
<h3>ANA MARIA<br>PEREZ LOPEZ</h3><span>ESTUDIANTE UNEMI</span>
<table>
<tr><td>CÉDULA</td><td>09••••••26</td></tr>
<tr><td>CARRERA</td><td>Biotecnología</td></tr>
<tr><td>FACULTAD</td><td>Facultad de Ciencias e Ingenierías - FACI</td></tr>
<tr><td>MODALIDAD</td><td>Presencial</td></tr>
<tr><td>NIVEL</td><td>Quinto Semestre</td></tr>
<tr><td>VIGENCIA</td><td>13 de agosto de 2026 – 22 de diciembre de 2026</td></tr>
</table></body></html>"""

DATOS_VALIDOS = sga.DatosSGA(
    valido=True, nombres="Ana Maria", apellidos="Perez Lopez", carrera="Biotecnología",
    facultad="Facultad de Ciencias e Ingenierías - FACI", modalidad="Presencial", nivel="Quinto Semestre",
    inicio_vigencia=date(2026, 8, 13), fin_vigencia=date(2099, 12, 22),
)


class LecturaPaginaSGATests(TestCase):
    def test_interpreta_los_datos_de_la_pagina(self):
        datos = sga.interpretar(HTML_VALIDO)
        self.assertTrue(datos.valido)
        self.assertEqual(datos.nombres, "Ana Maria")
        self.assertEqual(datos.apellidos, "Perez Lopez")
        self.assertEqual(datos.carrera, "Biotecnología")
        self.assertEqual(datos.nivel, "Quinto Semestre")
        self.assertEqual(datos.inicio_vigencia, date(2026, 8, 13))
        self.assertEqual(datos.fin_vigencia, date(2026, 12, 22))

    def test_detecta_un_carne_no_valido(self):
        self.assertFalse(sga.interpretar("<h2>Carné no válido</h2>").valido)


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=True)
class IdentificacionConSGATests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", "ClaveSegura-2026", nombres="Ana", apellidos="Prueba", rol=rol)

    @patch("estudiantes.sga.consultar", return_value=DATOS_VALIDOS)
    def test_carne_nuevo_se_completa_con_los_datos_del_sga(self, _consulta):
        resultado = identificar_por_qr(QR, self.docente)
        self.assertEqual(resultado.estado, "nuevo")
        carnet = resultado.carnet
        self.assertEqual(carnet.estado_registro, CarnetEstudiantil.REGISTRADO)
        self.assertEqual(carnet.estudiante.nombres, "Ana Maria")
        self.assertEqual(carnet.estudiante.carrera, "Biotecnología")
        self.assertIsNone(carnet.estudiante.cedula)  # la cédula oculta del SGA no se guarda (RNF06)

    @patch("estudiantes.sga.consultar", return_value=None)
    def test_si_el_sga_no_responde_el_carne_queda_pendiente(self, _consulta):
        resultado = identificar_por_qr(QR, self.docente)
        self.assertEqual(resultado.estado, "nuevo")
        self.assertTrue(resultado.permite_verificar)
        self.assertEqual(resultado.carnet.estado_registro, CarnetEstudiantil.PENDIENTE)

    @patch("estudiantes.sga.consultar", return_value=sga.DatosSGA(valido=False))
    def test_carne_no_valido_en_el_sga_no_se_registra(self, _consulta):
        resultado = identificar_por_qr(QR, self.docente)
        self.assertEqual(resultado.estado, "no_valido_sga")
        self.assertFalse(resultado.permite_verificar)
        self.assertEqual(CarnetEstudiantil.objects.count(), 0)

    def test_un_carne_pendiente_se_completa_al_volver_a_escanearlo(self):
        with patch("estudiantes.sga.consultar", return_value=None):
            identificar_por_qr(QR, self.docente)
        with patch("estudiantes.sga.consultar", return_value=DATOS_VALIDOS):
            resultado = identificar_por_qr(QR, self.docente)
        self.assertEqual(resultado.estado, "registrado")
        self.assertEqual(resultado.carnet.estudiante.apellidos, "Perez Lopez")
