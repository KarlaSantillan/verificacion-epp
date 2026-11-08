"""Pruebas de HU08: registro de ingresos e incidencias (RF07 – CP23 a CP26).

Ejecutar con:  python manage.py test verificacion
"""
import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import Auditoria
from configuracion.models import Epp, Laboratorio, LaboratorioEpp, ModeloVision, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil, Estudiante
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion, ValidacionDetalle

CLAVE = "ClaveSegura-2026"
TODOS = {"lab_coat": 0.9, "gloves": 0.9, "safety_glasses": 0.9, "mask": 0.9}


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False)
class RegistroValidacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=rol)
        cls.lab = Laboratorio.objects.create(nombre="Lab A", tiempo_estabilizacion_segundos=3)
        for clase, nombre in [("lab_coat", "Bata"), ("gloves", "Guantes"), ("safety_glasses", "Gafas"), ("mask", "Mascarilla")]:
            epp = Epp.objects.create(nombre=nombre, clase_modelo=clase)
            LaboratorioEpp.objects.create(laboratorio=cls.lab, epp=epp, confianza_minima=Decimal("0.80"))
        hoy = timezone.localdate()
        cls.periodo = PeriodoAcademico.objects.create(nombre="Actual", fecha_inicio=hoy - timedelta(days=30), fecha_fin=hoy + timedelta(days=30))
        cls.modelo = ModeloVision.objects.create(nombre="epp-yolov8", version="v1", activo=True)
        estudiante = Estudiante.objects.create(nombres="Ana", apellidos="Pérez")
        cls.carnet = CarnetEstudiantil.objects.create(
            usuario_registro=cls.docente, estudiante=estudiante, qr_hash="a" * 64, codigo_validacion="TEST0001",
            estado_registro=CarnetEstudiantil.REGISTRADO,
        )

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def registrar(self, clave="clave-1", **extra):
        datos = {"clave": clave, "carnet": self.carnet.pk, "laboratorio": self.lab.pk, "confianzas": TODOS, **extra}
        return self.client.post(reverse("verificacion:registrar"), json.dumps(datos), content_type="application/json")

    # CA01, CA05 (CP23)
    def test_cp23_cumple_se_registra_con_el_docente_como_supervisor(self):
        datos = self.registrar().json()
        self.assertTrue(datos["ok"])
        validacion = Validacion.objects.get()
        self.assertEqual(validacion.resultado_final, Validacion.CONFORME)
        self.assertEqual(validacion.resultado_modelo, Validacion.CONFORME)
        self.assertEqual(validacion.usuario_supervisor, self.docente)
        self.assertEqual(validacion.periodo, self.periodo)
        self.assertEqual(validacion.modelo, self.modelo)

    def test_el_registro_automatico_queda_en_auditoria_como_sistema(self):
        self.registrar()
        evento = Auditoria.objects.filter(tabla_afectada="epp_t_validacion").get()
        self.assertEqual(evento.tipo_actor, Auditoria.SISTEMA)

    # CA02 (CP24)
    def test_cp24_no_cumple_requiere_confirmacion(self):
        sin_guantes = {**TODOS, "gloves": 0.3}
        respuesta = self.registrar(confianzas=sin_guantes)
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Validacion.objects.exists())
        datos = self.registrar(confianzas=sin_guantes, confirmar_no_conforme=True).json()
        self.assertTrue(datos["ok"])
        self.assertEqual(Validacion.objects.get().resultado_final, Validacion.NO_CONFORME)
        evento = Auditoria.objects.filter(tabla_afectada="epp_t_validacion").get()
        self.assertEqual(evento.usuario, self.docente)

    # CA03 (CP25)
    def test_cp25_detalle_por_epp_con_confianza_y_umbral(self):
        self.registrar(confianzas={**TODOS, "mask": 0.5}, confirmar_no_conforme=True)
        detalles = ValidacionDetalle.objects.filter(validacion=Validacion.objects.get())
        self.assertEqual(detalles.count(), 4)
        mascarilla = detalles.get(epp__clase_modelo="mask")
        self.assertEqual(mascarilla.confianza, Decimal("0.5"))
        self.assertEqual(mascarilla.umbral_usado, Decimal("0.80"))
        self.assertFalse(mascarilla.detectado_modelo)
        self.assertTrue(mascarilla.requerido)

    # CA04 (CP26)
    def test_cp26_reintentar_con_la_misma_clave_no_duplica(self):
        primero = self.registrar(clave="misma").json()
        segundo = self.registrar(clave="misma").json()
        self.assertEqual(primero["id"], segundo["id"])
        self.assertTrue(segundo["repetido"])
        self.assertEqual(Validacion.objects.count(), 1)

    def test_el_servidor_recalcula_el_resultado(self):
        self.registrar(confianzas={**TODOS, "gloves": 0.1}, confirmar_no_conforme=True)
        self.assertEqual(Validacion.objects.get().resultado_final, Validacion.NO_CONFORME)

    # Situaciones que impiden registrar
    def test_sin_periodo_vigente_no_registra(self):
        PeriodoAcademico.objects.all().delete()
        respuesta = self.registrar()
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("periodo académico vigente", respuesta.json()["mensaje"])
        self.assertFalse(Validacion.objects.exists())

    def test_carne_inactivo_no_registra(self):
        self.carnet.activo = False
        self.carnet.save()
        self.assertEqual(self.registrar().status_code, 400)

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.registrar().status_code, 302)
