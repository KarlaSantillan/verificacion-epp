"""Pruebas del resumen de la clase al pulsar «Nueva práctica» y su envío por correo al docente.

Ejecutar con:  python manage.py test verificacion.tests_resumen_practica
"""
import json
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from configuracion.models import Laboratorio, ModeloVision, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil, Estudiante
from estudiantes.servicios import calcular_hash
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion

CLAVE = "ClaveSegura-2026"
CORREO_PRUEBAS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False, MAILERS=CORREO_PRUEBAS,
                   CORREO_REMITENTE="no-responder@unemi.edu.ec")
class ResumenPracticaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.dora = Usuario.objects.create_user("dora@unemi.edu.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=rol)
        cls.beto = Usuario.objects.create_user("beto@unemi.edu.ec", CLAVE, nombres="Beto", apellidos="Docente", rol=rol)
        cls.lab = Laboratorio.objects.create(nombre="Lab A")
        hoy = timezone.localdate()
        cls.periodo = PeriodoAcademico.objects.create(nombre="Actual", fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy + timedelta(days=60))
        cls.modelo = ModeloVision.objects.create(nombre="epp-yolov8", version="v2", activo=True)
        cls.carnets = []
        with override_settings(QR_HASH_KEY="clave-solo-para-pruebas"):
            for i, nombre in enumerate(["Ana", "Luis", "Eva"]):
                estudiante = Estudiante.objects.create(nombres=nombre, apellidos="Prueba")
                cls.carnets.append(CarnetEstudiantil.objects.create(
                    usuario_registro=cls.dora, estudiante=estudiante, qr_hash=calcular_hash(f"RES{i}"),
                    codigo_validacion=f"RES{i}", estado_registro=CarnetEstudiantil.REGISTRADO,
                ))

    def setUp(self):
        self.client.login(username="dora@unemi.edu.ec", password=CLAVE)
        self.practica("Microbiología", "Hongos")

    def practica(self, materia, practica, nueva=False):
        datos = {"materia": materia, "practica": practica, "nueva": nueva}
        return self.client.post(reverse("verificacion:sesion_practica"), json.dumps(datos), content_type="application/json")

    def validacion(self, carnet, resultado, supervisor=None, observacion="Materia: Microbiología | Práctica: Hongos"):
        return Validacion.objects.create(
            usuario_supervisor=supervisor or self.dora, periodo=self.periodo, modelo=self.modelo, carnet=carnet,
            laboratorio=self.lab, fecha_hora=timezone.now(), resultado_modelo=resultado, resultado_final=resultado,
            observacion=observacion,
        )

    def resumen(self):
        return self.client.get(reverse("verificacion:resumen_practica")).json()

    def test_sin_verificaciones_el_total_es_cero(self):
        self.assertEqual(self.resumen()["total"], 0)

    def test_cada_estudiante_se_cuenta_una_vez_con_su_ultimo_resultado(self):
        ana, luis, eva = self.carnets
        self.validacion(ana, Validacion.NO_CONFORME)
        self.validacion(ana, Validacion.CONFORME)  # corrigió en el momento
        self.validacion(luis, Validacion.CONFORME)
        self.validacion(eva, Validacion.NO_CONFORME)
        datos = self.resumen()
        self.assertEqual(datos["total"], 3)
        self.assertIn("Eva Prueba", datos["html"])     # no cumplió
        self.assertIn("Corrigieron en el momento", datos["html"])

    def test_no_incluye_otras_practicas_ni_otros_docentes(self):
        ana, luis, eva = self.carnets
        self.validacion(ana, Validacion.CONFORME)
        self.validacion(luis, Validacion.CONFORME, observacion="Materia: Química | Práctica: Ácidos")
        self.validacion(eva, Validacion.CONFORME, supervisor=self.beto)
        self.assertEqual(self.resumen()["total"], 1)

    def test_nueva_practica_reinicia_el_resumen(self):
        self.validacion(self.carnets[0], Validacion.CONFORME)
        self.assertEqual(self.resumen()["total"], 1)
        self.practica("", "", nueva=True)
        self.practica("Microbiología", "Hongos")  # misma práctica, pero otra clase
        self.assertEqual(self.resumen()["total"], 0)

    def test_enviar_resumen_por_correo_al_docente(self):
        self.validacion(self.carnets[0], Validacion.NO_CONFORME)
        respuesta = self.client.post(reverse("verificacion:resumen_practica_enviar"))
        self.assertTrue(respuesta.json()["ok"])
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["dora@unemi.edu.ec"])
        self.assertIn("Microbiología", correo.subject)
        self.assertIn("Ana Prueba", correo.alternatives[0][0])

    def test_enviar_sin_verificaciones_da_error(self):
        respuesta = self.client.post(reverse("verificacion:resumen_practica_enviar"))
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_si_falla_el_correo_avisa_sin_romper(self):
        self.validacion(self.carnets[0], Validacion.CONFORME)
        with mock.patch("verificacion.views_resumen.EmailMultiAlternatives.send", side_effect=OSError("sin internet")), \
                self.assertLogs("verificacion.views_resumen", level="ERROR"):
            respuesta = self.client.post(reverse("verificacion:resumen_practica_enviar"))
        self.assertEqual(respuesta.status_code, 502)
        self.assertFalse(respuesta.json()["ok"])

    def test_documento_para_imprimir(self):
        self.validacion(self.carnets[0], Validacion.NO_CONFORME)
        respuesta = self.client.get(reverse("verificacion:resumen_practica_imprimir"))
        self.assertContains(respuesta, "RESUMEN DE PRÁCTICA DE LABORATORIO")
        self.assertContains(respuesta, "UNIVERSIDAD ESTATAL DE MILAGRO")
        self.assertContains(respuesta, "Ana Prueba")

    # --- Sección «Prácticas» (prácticas anteriores)
    def test_lista_de_practicas_anteriores(self):
        ana, luis, eva = self.carnets
        self.validacion(ana, Validacion.CONFORME)
        self.validacion(luis, Validacion.NO_CONFORME, observacion="Materia: Química | Práctica: Ácidos")
        self.validacion(eva, Validacion.CONFORME, supervisor=self.beto)  # de otro docente: no se ve
        respuesta = self.client.get(reverse("historial:practicas"))
        self.assertEqual(respuesta.context["pagina"].paginator.count, 2)
        self.assertContains(respuesta, "Química")
        self.assertNotContains(respuesta, "Eva Prueba")

    def test_misma_practica_separada_por_mas_de_dos_horas(self):
        ana, luis, _ = self.carnets
        manana = self.validacion(ana, Validacion.CONFORME)
        Validacion.objects.filter(pk=manana.pk).update(fecha_hora=timezone.now() - timedelta(hours=3))
        self.validacion(luis, Validacion.CONFORME)
        self.assertEqual(self.client.get(reverse("historial:practicas")).context["pagina"].paginator.count, 2)

    def test_ver_resumen_de_practica_anterior(self):
        self.validacion(self.carnets[0], Validacion.NO_CONFORME)
        practica = self.client.get(reverse("historial:practicas")).context["pagina"][0]
        respuesta = self.client.get(reverse("verificacion:resumen_practica_imprimir") + "?" + practica.consulta)
        self.assertContains(respuesta, "Ana Prueba")

    def test_un_docente_no_ve_practicas_de_otro(self):
        self.validacion(self.carnets[0], Validacion.CONFORME, supervisor=self.beto)
        ahora = timezone.now()
        url = reverse("verificacion:resumen_practica_imprimir")
        respuesta = self.client.get(url, {"docente": self.beto.pk, "desde": (ahora - timedelta(hours=1)).isoformat(),
                                          "hasta": (ahora + timedelta(hours=1)).isoformat(), "materia": "Microbiología", "practica": "Hongos"})
        self.assertEqual(respuesta.status_code, 404)
