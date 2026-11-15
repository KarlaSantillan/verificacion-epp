"""Pruebas de Materia y Práctica (sugerencia de la asesoría del 12/11/2026).

Ejecutar con:  python manage.py test verificacion.tests_materia_practica
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
from historial.filtros import filtrar_validaciones, leer_filtros
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion
from verificacion.sesion_practica import componer, limpiar, separar

CLAVE = "ClaveSegura-2026"
TODOS = {"lab_coat": 0.9, "gloves": 0.9, "safety_glasses": 0.9, "mask": 0.9}


@override_settings(QR_HASH_KEY="clave-solo-para-pruebas", SGA_CONSULTA_ACTIVA=False)
class MateriaPracticaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=rol)
        cls.lab = Laboratorio.objects.create(nombre="Lab A", tiempo_estabilizacion_segundos=3)
        for clase, nombre in [("lab_coat", "Bata"), ("gloves", "Guantes"), ("safety_glasses", "Gafas"), ("mask", "Mascarilla")]:
            epp = Epp.objects.create(nombre=nombre, clase_modelo=clase)
            LaboratorioEpp.objects.create(laboratorio=cls.lab, epp=epp, confianza_minima=Decimal("0.80"))
        hoy = timezone.localdate()
        PeriodoAcademico.objects.create(nombre="Actual", fecha_inicio=hoy - timedelta(days=30), fecha_fin=hoy + timedelta(days=30))
        ModeloVision.objects.create(nombre="epp-yolov8", version="v1", activo=True)
        estudiante = Estudiante.objects.create(nombres="Ana", apellidos="Pérez")
        cls.carnet = CarnetEstudiantil.objects.create(
            usuario_registro=cls.docente, estudiante=estudiante, qr_hash="a" * 64, codigo_validacion="TEST0001",
            estado_registro=CarnetEstudiantil.REGISTRADO,
        )

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def fijar_sesion(self, materia, practica):
        datos = {"materia": materia, "practica": practica}
        return self.client.post(reverse("verificacion:sesion_practica"), json.dumps(datos), content_type="application/json")

    def registrar(self, clave):
        datos = {"clave": clave, "carnet": self.carnet.pk, "laboratorio": self.lab.pk, "confianzas": TODOS}
        return self.client.post(reverse("verificacion:registrar"), json.dumps(datos), content_type="application/json")

    def test_limpiar_componer_y_separar(self):
        self.assertEqual(limpiar("  Micro   biología ", 100), "Micro biología")
        self.assertEqual(len(limpiar("x" * 300, 150)), 150)
        self.assertEqual(limpiar(None, 100), "")
        texto = componer("Microbiología", "Tinción | de Gram")
        self.assertEqual(texto, "Materia: Microbiología | Práctica: Tinción / de Gram")
        self.assertEqual(separar(texto), ("Microbiología", "Tinción / de Gram"))
        self.assertEqual(separar(componer("", "Electroforesis")), ("", "Electroforesis"))
        self.assertEqual(componer("", ""), "")
        self.assertEqual(separar(None), ("", ""))

    def test_la_validacion_guarda_la_materia_y_practica_de_la_sesion(self):
        respuesta = self.fijar_sesion(" Microbiología ", "Tinción de Gram")
        self.assertTrue(respuesta.json()["ok"])
        self.assertTrue(self.registrar("c1").json()["ok"])
        validacion = Validacion.objects.get()
        self.assertEqual(validacion.observacion, "Materia: Microbiología | Práctica: Tinción de Gram")

    def test_sin_materia_ni_practica_se_guarda_vacio(self):
        self.assertTrue(self.registrar("c1").json()["ok"])
        self.assertIsNone(Validacion.objects.get().observacion)

    def test_cambiar_la_sesion_solo_afecta_a_las_siguientes(self):
        self.fijar_sesion("Microbiología", "Tinción de Gram")
        self.registrar("c1")
        self.fijar_sesion("Bioquímica", "Electroforesis")
        self.registrar("c2")
        materias = [separar(t)[0] for t in Validacion.objects.order_by("id_validacion").values_list("observacion", flat=True)]
        self.assertEqual(materias, ["Microbiología", "Bioquímica"])

    def test_filtro_del_historial_por_materia_y_practica(self):
        self.fijar_sesion("Microbiología", "Tinción de Gram")
        self.registrar("c1")
        self.fijar_sesion("Bioquímica", "Electroforesis")
        self.registrar("c2")
        filtros = leer_filtros({"materia": "micro"})
        self.assertEqual([separar(v.observacion)[0] for v in filtrar_validaciones(filtros)], ["Microbiología"])
        filtros = leer_filtros({"practica": "electro"})
        self.assertEqual([separar(v.observacion)[1] for v in filtrar_validaciones(filtros)], ["Electroforesis"])
        # "gram" está en la práctica, no en la materia: el filtro de materia no debe encontrarlo
        self.assertFalse(filtrar_validaciones(leer_filtros({"materia": "gram"})).exists())

    def test_editar_desde_el_detalle_no_cambia_el_resultado_y_queda_en_auditoria(self):
        self.registrar("c1")
        validacion = Validacion.objects.get()
        url = reverse("historial:editar_practica", args=[validacion.pk])
        respuesta = self.client.post(url, {"materia": "Genética", "practica": "Extracción de ADN"})
        self.assertEqual(respuesta.status_code, 302)
        validacion.refresh_from_db()
        self.assertEqual(separar(validacion.observacion), ("Genética", "Extracción de ADN"))
        self.assertEqual(validacion.resultado_final, Validacion.CONFORME)
        evento = Auditoria.objects.filter(tabla_afectada="epp_t_validacion", accion="UPDATE").get()
        self.assertEqual(evento.datos_nuevos, {"observacion": "Materia: Genética | Práctica: Extracción de ADN"})
        self.assertEqual(evento.usuario, self.docente)

    def test_editar_requiere_post(self):
        self.registrar("c1")
        url = reverse("historial:editar_practica", args=[Validacion.objects.get().pk])
        self.assertEqual(self.client.get(url).status_code, 405)
