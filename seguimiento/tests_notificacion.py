"""Pruebas del correo institucional del estudiante y de la notificación del llamado de atención (HU16).

Ejecutar con:  python manage.py test seguimiento.tests_notificacion
"""
import json
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from configuracion.models import Laboratorio, ModeloVision, Parametro, PeriodoAcademico
from estudiantes.forms import validar_correo_unemi
from estudiantes.models import CarnetEstudiantil, Estudiante
from estudiantes.servicios import calcular_hash, ocultar_correo
from auditoria.models import Auditoria
from seguimiento.models import LlamadoAtencion
from seguimiento.notificacion import ACCION_AUDITORIA
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion

CLAVE = "ClaveSegura-2026"
CORREO_PRUEBAS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False, MAILERS=CORREO_PRUEBAS,
                   CORREO_REMITENTE="no-responder@unemi.edu.ec")
class NotificacionLlamadoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=rol)
        cls.lab = Laboratorio.objects.create(nombre="Lab A")
        hoy = timezone.localdate()
        cls.periodo = PeriodoAcademico.objects.create(nombre="Actual", fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy + timedelta(days=60))
        cls.modelo = ModeloVision.objects.create(nombre="epp-yolov8", version="v2", activo=True)
        Parametro.objects.create(clave="umbral_incidencias", valor="3")
        cls.estudiante = Estudiante.objects.create(nombres="Ana", apellidos="Pérez", cedula="0911111111", carrera="Biotecnología")
        with override_settings(QR_HASH_KEY="clave-solo-para-pruebas"):
            cls.carnet = CarnetEstudiantil.objects.create(
                usuario_registro=cls.docente, estudiante=cls.estudiante, qr_hash=calcular_hash("CORR0001"),
                codigo_validacion="CORR0001", estado_registro=CarnetEstudiantil.REGISTRADO,
            )

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def reincidente(self):
        for minutos in (-30, -20, -10):
            Validacion.objects.create(
                usuario_supervisor=self.docente, periodo=self.periodo, modelo=self.modelo, carnet=self.carnet, laboratorio=self.lab,
                fecha_hora=timezone.now() + timedelta(minutes=minutos),
                resultado_modelo=Validacion.NO_CONFORME, resultado_final=Validacion.NO_CONFORME,
            )

    def llamar(self, observacion="Se conversó con la estudiante sobre el uso de guantes."):
        url = reverse("historial:llamado", args=[self.estudiante.pk]) + f"?periodo={self.periodo.pk}"
        return self.client.post(url, {"observacion": observacion}, follow=True)

    def con_correo(self, correo="aperez5@unemi.edu.ec"):
        self.estudiante.correo = correo
        self.estudiante.save()

    # --- Validación del correo
    def test_correo_institucional_valido_y_normalizado(self):
        self.assertEqual(validar_correo_unemi("  APerez5@UNEMI.edu.ec "), "aperez5@unemi.edu.ec")
        self.assertEqual(validar_correo_unemi(""), "")

    def test_correo_de_otro_dominio_se_rechaza(self):
        from django import forms
        for valor in ("ana@gmail.com", "ana@unemi.edu.ec.com", "no-es-correo"):
            with self.assertRaises(forms.ValidationError):
                validar_correo_unemi(valor)

    def test_correo_enmascarado(self):
        self.assertEqual(ocultar_correo("ksantillanc3@unemi.edu.ec"), "ks••••••••c3@unemi.edu.ec")
        self.assertIsNone(ocultar_correo(None))

    # --- Registro del correo desde la verificación
    def test_identificar_devuelve_id_y_correo_enmascarado(self):
        self.con_correo()
        datos = self.client.post(reverse("verificacion:identificar"), json.dumps({"codigo": "CORR0001"}), content_type="application/json").json()
        self.assertEqual(datos["estudiante"]["id"], self.estudiante.pk)
        self.assertEqual(datos["estudiante"]["correo"], "ap•••z5@unemi.edu.ec")
        self.assertNotIn("aperez5", datos["estudiante"]["correo"])

    def test_guardar_correo_cuando_no_tiene(self):
        r = self.client.post(reverse("verificacion:correo_estudiante"),
                             json.dumps({"estudiante": self.estudiante.pk, "correo": "APerez5@unemi.edu.ec"}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.estudiante.refresh_from_db()
        self.assertEqual(self.estudiante.correo, "aperez5@unemi.edu.ec")

    def test_no_se_sobrescribe_un_correo_existente(self):
        self.con_correo()
        r = self.client.post(reverse("verificacion:correo_estudiante"),
                             json.dumps({"estudiante": self.estudiante.pk, "correo": "otro1@unemi.edu.ec"}), content_type="application/json")
        self.assertEqual(r.status_code, 409)
        self.estudiante.refresh_from_db()
        self.assertEqual(self.estudiante.correo, "aperez5@unemi.edu.ec")

    def test_guardar_correo_de_otro_dominio_da_error(self):
        r = self.client.post(reverse("verificacion:correo_estudiante"),
                             json.dumps({"estudiante": self.estudiante.pk, "correo": "ana@gmail.com"}), content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.estudiante.refresh_from_db()
        self.assertIsNone(self.estudiante.correo)

    # --- Notificación del llamado (opción B)
    def test_llamado_con_correo_envia_notificacion(self):
        self.con_correo()
        self.reincidente()
        respuesta = self.llamar()
        self.assertEqual(LlamadoAtencion.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["aperez5@unemi.edu.ec"])
        self.assertIn("Se conversó con la estudiante", correo.body)
        self.assertNotIn("0911111111", correo.body)  # sin cédula (LOPDP)
        html = correo.alternatives[0][0]
        self.assertIn("Sistema de Verificación de EPP", html)
        self.assertIn("Se conversó con la estudiante", html)
        self.assertNotIn("0911111111", html)
        self.assertContains(respuesta, "Se notificó al estudiante")

    def test_llamado_sin_correo_se_registra_y_avisa(self):
        self.reincidente()
        respuesta = self.llamar()
        self.assertEqual(LlamadoAtencion.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(respuesta, "no tiene correo registrado")

    def test_si_falla_el_envio_el_llamado_igual_se_guarda(self):
        self.con_correo()
        self.reincidente()
        with mock.patch("seguimiento.notificacion.EmailMultiAlternatives.send", side_effect=OSError("SMTP caído")), \
                self.assertLogs("seguimiento.notificacion", level="ERROR"):  # el error queda en el log, sin ensuciar la salida
            respuesta = self.llamar()
        self.assertEqual(LlamadoAtencion.objects.count(), 1)
        self.assertContains(respuesta, "No se pudo enviar el correo")

    def test_llamado_no_valido_no_envia_correo(self):
        self.con_correo()
        self.reincidente()
        self.llamar(observacion="")
        self.assertEqual(LlamadoAtencion.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    # --- Reenvío cuando no había internet (RNF10) y trazabilidad (RNF07)
    def notificaciones(self):
        return Auditoria.objects.filter(accion=ACCION_AUDITORIA).order_by("pk")

    def test_sin_internet_se_puede_reenviar_despues(self):
        self.con_correo()
        self.reincidente()
        with mock.patch("seguimiento.notificacion.EmailMultiAlternatives.send", side_effect=OSError("sin internet")), \
                self.assertLogs("seguimiento.notificacion", level="ERROR"):
            self.llamar()
        registro = LlamadoAtencion.objects.get()
        self.assertEqual(self.notificaciones().last().datos_nuevos["resultado"], "error")
        historial = self.client.get(reverse("historial:reincidente", args=[self.estudiante.pk]) + f"?periodo={self.periodo.pk}")
        self.assertContains(historial, "No se pudo enviar la notificación")
        respuesta = self.client.post(reverse("historial:reenviar_notificacion", args=[registro.pk]), follow=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(respuesta, "Se notificó al estudiante")
        self.assertEqual(self.notificaciones().last().datos_nuevos["resultado"], "enviado")
        self.assertContains(respuesta, "Notificación enviada")

    def test_la_auditoria_no_guarda_el_correo_completo(self):
        self.con_correo()
        self.reincidente()
        self.llamar()
        evento = self.notificaciones().get()
        self.assertEqual(evento.usuario, self.docente)
        self.assertNotIn("aperez5", str(evento.datos_nuevos))

    def test_reenviar_solo_por_post(self):
        self.con_correo()
        self.reincidente()
        self.llamar()
        registro = LlamadoAtencion.objects.get()
        self.assertEqual(self.client.get(reverse("historial:reenviar_notificacion", args=[registro.pk])).status_code, 405)
