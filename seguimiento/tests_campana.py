"""Pruebas de la campana que se actualiza sola y del filtro «Solo mis verificaciones».

Ejecutar con:  python manage.py test seguimiento.tests_campana
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from configuracion.models import Laboratorio, ModeloVision, Parametro, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil, Estudiante
from estudiantes.servicios import calcular_hash
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion

CLAVE = "ClaveSegura-2026"


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False)
class CampanaYFiltroTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        docente = Rol.objects.create(nombre=Rol.DOCENTE)
        admin = Rol.objects.create(nombre=Rol.ADMINISTRADOR)
        cls.dora = Usuario.objects.create_user("dora@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=docente)
        cls.beto = Usuario.objects.create_user("beto@prueba.ec", CLAVE, nombres="Beto", apellidos="Docente", rol=docente)
        cls.admin = Usuario.objects.create_user("admin@prueba.ec", CLAVE, nombres="Ada", apellidos="Admin", rol=admin)
        cls.lab = Laboratorio.objects.create(nombre="Lab A")
        hoy = timezone.localdate()
        cls.periodo = PeriodoAcademico.objects.create(nombre="Actual", fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy + timedelta(days=60))
        cls.modelo = ModeloVision.objects.create(nombre="epp-yolov8", version="v2", activo=True)
        Parametro.objects.create(clave="umbral_incidencias", valor="3")
        cls.estudiante = Estudiante.objects.create(nombres="Ana", apellidos="Pérez", cedula="0911111111")
        with override_settings(QR_HASH_KEY="clave-solo-para-pruebas"):
            cls.carnet = CarnetEstudiantil.objects.create(
                usuario_registro=cls.dora, estudiante=cls.estudiante, qr_hash=calcular_hash("CAMP0001"),
                codigo_validacion="CAMP0001", estado_registro=CarnetEstudiantil.REGISTRADO,
            )

    def incidencia(self, supervisor, minutos):
        return Validacion.objects.create(
            usuario_supervisor=supervisor, periodo=self.periodo, modelo=self.modelo, carnet=self.carnet, laboratorio=self.lab,
            fecha_hora=timezone.now() - timedelta(minutes=minutos),
            resultado_modelo=Validacion.NO_CONFORME, resultado_final=Validacion.NO_CONFORME,
        )

    def entrar(self, correo):
        self.client.login(username=correo, password=CLAVE)

    # --- Campana
    def test_campana_sin_pendientes(self):
        self.entrar("dora@prueba.ec")
        datos = self.client.get(reverse("seguimiento:notificaciones")).json()
        self.assertEqual(datos["total"], 0)
        self.assertEqual(datos["estudiantes"], [])
        self.assertIn("No hay estudiantes", datos["html"])

    def test_campana_cuenta_incidencias_de_todos_los_docentes(self):
        # Una incidencia de Beto y dos de Dora: la estudiante llega al umbral (3) aunque nadie tenga 3.
        self.incidencia(self.beto, 30)
        self.incidencia(self.dora, 20)
        self.incidencia(self.dora, 10)
        self.entrar("dora@prueba.ec")
        datos = self.client.get(reverse("seguimiento:notificaciones")).json()
        self.assertEqual(datos["total"], 1)
        self.assertEqual(datos["estudiantes"][0]["id"], self.estudiante.pk)
        self.assertIn("Ana", datos["html"])

    def test_campana_requiere_sesion(self):
        respuesta = self.client.get(reverse("seguimiento:notificaciones"))
        self.assertEqual(respuesta.status_code, 302)

    def test_la_pagina_incluye_el_script_de_la_campana(self):
        self.entrar("dora@prueba.ec")
        respuesta = self.client.get(reverse("historial:registros"))
        self.assertContains(respuesta, "js/campana.js")
        self.assertContains(respuesta, 'id="campana"')

    # --- Filtro «Solo mis verificaciones»
    def test_docente_ve_solo_las_suyas_por_defecto(self):
        mia, ajena = self.incidencia(self.dora, 20), self.incidencia(self.beto, 10)
        self.entrar("dora@prueba.ec")
        respuesta = self.client.get(reverse("historial:registros"))
        ids = [v.pk for v in respuesta.context["pagina"]]
        self.assertIn(mia.pk, ids)
        self.assertNotIn(ajena.pk, ids)
        self.assertContains(respuesta, "solo las verificaciones que usted supervisó")

    def test_docente_puede_ver_las_de_todos(self):
        mia, ajena = self.incidencia(self.dora, 20), self.incidencia(self.beto, 10)
        self.entrar("dora@prueba.ec")
        ids = [v.pk for v in self.client.get(reverse("historial:registros"), {"mios": "0"}).context["pagina"]]
        self.assertEqual(set(ids), {mia.pk, ajena.pk})

    def test_administrador_ve_todas_por_defecto(self):
        self.incidencia(self.dora, 20)
        self.incidencia(self.beto, 10)
        self.entrar("admin@prueba.ec")
        self.assertEqual(self.client.get(reverse("historial:registros")).context["pagina"].paginator.count, 2)

    def test_el_csv_respeta_el_filtro(self):
        self.incidencia(self.dora, 20)
        self.incidencia(self.beto, 10)
        self.entrar("dora@prueba.ec")
        contenido = self.client.get(reverse("historial:registros_csv")).content.decode("utf-8-sig")
        filas = [linea for linea in contenido.splitlines() if linea.strip()]
        self.assertEqual(len(filas), 2)  # encabezado + 1 fila (solo la de Dora)
