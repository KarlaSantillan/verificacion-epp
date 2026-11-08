"""Pruebas de HU15 (reincidentes y notificaciones) y HU16 (llamado de atención y CSV).

Ejecutar con:  python manage.py test seguimiento
"""
import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import Auditoria
from configuracion.models import Laboratorio, ModeloVision, Parametro, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil, Estudiante
from estudiantes.servicios import calcular_hash
from seguimiento.models import LlamadoAtencion
from seguimiento.reincidencia import OBSERVACION, REGISTRADO, REQUIERE, pendientes_de_llamado, reincidentes
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion

CLAVE = "ClaveSegura-2026"


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False)
class ReincidenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=rol)
        cls.lab = Laboratorio.objects.create(nombre="Lab A")
        hoy = timezone.localdate()
        cls.periodo = PeriodoAcademico.objects.create(nombre="Actual", fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy + timedelta(days=60))
        cls.modelo = ModeloVision.objects.create(nombre="epp-yolov8", version="v1", activo=True)
        cls.parametro = Parametro.objects.create(clave="umbral_incidencias", valor="3")
        cls.estudiante = Estudiante.objects.create(nombres="Ana", apellidos="Pérez", cedula="0911111111", carrera="Biotecnología")
        with override_settings(QR_HASH_KEY="clave-solo-para-pruebas"):
            cls.carnet = CarnetEstudiantil.objects.create(
                usuario_registro=cls.docente, estudiante=cls.estudiante, qr_hash=calcular_hash("REIN0001"),
                codigo_validacion="REIN0001", estado_registro=CarnetEstudiantil.REGISTRADO,
            )

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def incidencia(self, minutos, final=Validacion.NO_CONFORME):
        return Validacion.objects.create(
            usuario_supervisor=self.docente, periodo=self.periodo, modelo=self.modelo, carnet=self.carnet, laboratorio=self.lab,
            fecha_hora=timezone.now() + timedelta(minutes=minutos), resultado_modelo=Validacion.NO_CONFORME, resultado_final=final,
        )

    def estado(self):
        lista = reincidentes(self.periodo)
        return lista[0].estado if lista else None

    def llamar(self, observacion="Se conversó con la estudiante sobre el uso de guantes."):
        return self.client.post(reverse("historial:llamado", args=[self.estudiante.pk]) + f"?periodo={self.periodo.pk}", {"observacion": observacion})

    # --- HU15 / RF12
    def test_cp35_al_llegar_al_umbral_requiere_llamado_y_notifica(self):
        self.incidencia(-30)
        self.incidencia(-20)
        self.assertEqual(self.estado(), OBSERVACION)
        self.assertEqual(len(pendientes_de_llamado()[1]), 0)
        self.incidencia(-10)
        self.assertEqual(self.estado(), REQUIERE)
        self.assertEqual(len(pendientes_de_llamado()[1]), 1)
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertEqual(respuesta.context["total_notificaciones"], 1)

    def test_cp36_las_corregidas_a_cumple_no_cuentan(self):
        self.incidencia(-30)
        self.incidencia(-20)
        self.incidencia(-10, final=Validacion.CONFORME)  # corregida
        self.assertEqual(reincidentes(self.periodo)[0].total, 2)
        self.assertEqual(self.estado(), OBSERVACION)

    def test_cp37_aviso_en_la_verificacion_sin_bloquear(self):
        for minutos in (-30, -20, -10):
            self.incidencia(minutos)
        datos = self.client.post(reverse("verificacion:identificar"), json.dumps({"codigo": "REIN0001"}), content_type="application/json").json()
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["reincidencia"], {"estado": REQUIERE, "incidencias": 3})

    def test_cp38_cambiar_el_umbral_recalcula(self):
        self.incidencia(-30)
        self.incidencia(-20)
        self.assertEqual(self.estado(), OBSERVACION)
        self.parametro.valor = "2"
        self.parametro.save()
        self.assertEqual(self.estado(), REQUIERE)

    def test_pestana_de_reincidentes(self):
        for minutos in (-30, -20, -10):
            self.incidencia(minutos)
        respuesta = self.client.get(reverse("historial:incidencias"), {"tab": "reincidentes"})
        self.assertContains(respuesta, "Ana Pérez")
        self.assertContains(respuesta, "Registrar llamado de atención")

    # --- HU16 / RF13
    def test_cp39_registrar_llamado(self):
        for minutos in (-30, -20, -10):
            self.incidencia(minutos)
        self.llamar()
        llamado = LlamadoAtencion.objects.get()
        self.assertEqual((llamado.cantidad_incidencias, llamado.usuario, llamado.periodo), (3, self.docente, self.periodo))
        self.assertEqual(self.estado(), REGISTRADO)
        self.assertEqual(len(pendientes_de_llamado()[1]), 0)
        self.assertTrue(Auditoria.objects.filter(tabla_afectada="epp_t_llamado_atencion", usuario=self.docente).exists())

    def test_cp40_sin_observacion_no_se_guarda(self):
        for minutos in (-30, -20, -10):
            self.incidencia(minutos)
        respuesta = self.llamar("   ")
        self.assertContains(respuesta, "La observación es obligatoria")
        self.assertFalse(LlamadoAtencion.objects.exists())

    def test_cp41_vuelve_a_requerir_al_acumular_otra_vez_el_umbral(self):
        for minutos in (-30, -20, -10):
            self.incidencia(minutos)
        self.llamar()
        self.incidencia(10)
        self.incidencia(20)
        self.assertEqual(self.estado(), OBSERVACION)
        self.incidencia(30)
        self.assertEqual(self.estado(), REQUIERE)
        self.assertEqual(reincidentes(self.periodo)[0].total, 6)

    def test_no_se_registra_llamado_si_no_lo_requiere(self):
        self.incidencia(-10)
        respuesta = self.llamar()
        self.assertContains(respuesta, "no requiere un llamado")
        self.assertFalse(LlamadoAtencion.objects.exists())

    def test_cp42_csv_de_reincidentes(self):
        for minutos in (-30, -20, -10):
            self.incidencia(minutos)
        respuesta = self.client.get(reverse("historial:reincidentes_csv"), {"periodo": self.periodo.pk})
        contenido = respuesta.content.decode("utf-8")
        self.assertTrue(contenido.startswith("﻿"))
        self.assertIn("incidencias_desde_ultimo_llamado", contenido)
        self.assertIn("Ana Pérez;09••••••11;Biotecnología;Actual;Todos;3;3", contenido)
        self.assertNotIn("0911111111", contenido)  # la cédula va enmascarada
