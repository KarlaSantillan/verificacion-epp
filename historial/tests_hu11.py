"""Pruebas de HU11: exportación de registros a CSV (RF10 – CP32).

Ejecutar con:  python manage.py test historial
"""
import csv
import io
from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from configuracion.models import Epp, Laboratorio, ModeloVision, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil, Estudiante
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion, ValidacionDetalle

CLAVE = "ClaveSegura-2026"


def momento(dia, hora=10):
    return timezone.make_aware(datetime(2026, 11, dia, hora, 0))


class ExportacionCsvTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=rol)
        cls.lab_a = Laboratorio.objects.create(nombre="Lab A")
        cls.lab_b = Laboratorio.objects.create(nombre="Lab B")
        cls.bata = Epp.objects.create(nombre="Bata", clase_modelo="lab_coat")
        cls.guantes = Epp.objects.create(nombre="Guantes", clase_modelo="gloves")
        cls.periodo = PeriodoAcademico.objects.create(nombre="2026-2", fecha_inicio="2026-08-13", fecha_fin="2026-12-22")
        cls.modelo = ModeloVision.objects.create(nombre="epp-yolov8", version="v1", activo=True)
        cls.ana = cls.crear_carnet("Ana María", "Pérez Núñez", "0911111111", "A1")
        cls.luis = cls.crear_carnet("=Luis", "Mora", "0922222222", "B2")  # nombre "peligroso" para Excel
        cls.v1 = cls.crear_validacion(cls.ana, cls.lab_a, 3, guantes=True)
        cls.v2 = cls.crear_validacion(cls.ana, cls.lab_a, 5, guantes=False)
        cls.v3 = cls.crear_validacion(cls.luis, cls.lab_b, 5, guantes=False)

    @classmethod
    def crear_carnet(cls, nombres, apellidos, cedula, codigo):
        estudiante = Estudiante.objects.create(nombres=nombres, apellidos=apellidos, cedula=cedula, carrera="Biotecnología")
        return CarnetEstudiantil.objects.create(
            usuario_registro=cls.docente, estudiante=estudiante, qr_hash=codigo * 32, codigo_validacion=codigo,
            estado_registro=CarnetEstudiantil.REGISTRADO,
        )

    @classmethod
    def crear_validacion(cls, carnet, laboratorio, dia, guantes):
        resultado = Validacion.CONFORME if guantes else Validacion.NO_CONFORME
        validacion = Validacion.objects.create(
            usuario_supervisor=cls.docente, periodo=cls.periodo, modelo=cls.modelo, carnet=carnet, laboratorio=laboratorio,
            fecha_hora=momento(dia), resultado_modelo=resultado, resultado_final=resultado,
        )
        for epp, detectado in [(cls.bata, True), (cls.guantes, guantes)]:
            ValidacionDetalle.objects.create(
                validacion=validacion, epp=epp, requerido=True, detectado_modelo=detectado, detectado_final=detectado,
                confianza=Decimal("0.90") if detectado else Decimal("0.40"), umbral_usado=Decimal("0.80"),
            )
        return validacion

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def descargar(self, nombre="registros_csv", **filtros):
        respuesta = self.client.get(reverse(f"historial:{nombre}"), filtros)
        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.content.decode("utf-8")
        filas = list(csv.DictReader(io.StringIO(texto.lstrip("﻿")), delimiter=";"))
        return respuesta, texto, filas

    def ids(self, filas):
        return {int(f["id_validacion"]) for f in filas}

    # CA01 (CP32): exactamente las filas de la consulta filtrada
    def test_cp32_mismas_filas_que_la_pantalla_con_filtros(self):
        filtros = {"laboratorio": self.lab_a.pk, "desde": "2026-11-04", "hasta": "2026-11-06", "estado": "no_conforme"}
        pantalla = self.client.get(reverse("historial:registros"), filtros).context["pagina"]
        _, _, filas = self.descargar(**filtros)
        self.assertEqual(self.ids(filas), {v.pk for v in pantalla})
        self.assertEqual(self.ids(filas), {self.v2.pk})

    def test_sin_filtros_exporta_todo_aunque_haya_varias_paginas(self):
        for dia in range(6, 30):  # 24 más → 27 en total; la pantalla muestra 20 por página
            self.crear_validacion(self.luis, self.lab_b, dia, guantes=True)
        _, _, filas = self.descargar()
        self.assertEqual(len(filas), Validacion.objects.count())

    def test_busqueda_por_estudiante(self):
        _, _, filas = self.descargar(q="0911111111")
        self.assertEqual(self.ids(filas), {self.v1.pk, self.v2.pk})

    def test_incidencias_solo_no_cumple(self):
        _, _, filas = self.descargar("incidencias_csv")
        self.assertEqual(self.ids(filas), {self.v2.pk, self.v3.pk})
        self.assertTrue(all(f["resultado_final"] == "No cumple" for f in filas))

    # CA02: Excel con tildes y columnas correctas
    def test_compatible_con_excel(self):
        respuesta, texto, filas = self.descargar()
        self.assertTrue(texto.startswith("﻿"))
        self.assertIn("text/csv", respuesta["Content-Type"])
        self.assertIn('attachment; filename="registros_epp_', respuesta["Content-Disposition"])
        self.assertIn("Ana María Pérez Núñez", texto)
        primera_linea = texto.lstrip("﻿").splitlines()[0]
        self.assertIn("id_validacion;fecha;hora;estudiante", primera_linea)

    # RF10-CA03: fecha y hora de Ecuador, resultados y estado de cada EPP
    def test_contenido_de_las_columnas(self):
        _, _, filas = self.descargar(q="Ana", estado="no_conforme")
        fila = filas[0]
        self.assertEqual((fila["fecha"], fila["hora"]), ("05/11/2026", "10:00:00"))
        self.assertEqual((fila["laboratorio"], fila["periodo"]), ("Lab A", "2026-2"))
        self.assertEqual((fila["resultado_modelo"], fila["resultado_final"]), ("No cumple", "No cumple"))
        self.assertEqual(fila["epp_Bata"], "Detectado")
        self.assertEqual(fila["epp_Guantes"], "No detectado")
        self.assertEqual(fila["epp_faltantes"], "Guantes")

    def test_una_correccion_se_ve_en_el_csv(self):
        detalle = self.v2.detalles.get(epp=self.guantes)
        detalle.detectado_final = True
        detalle.save()
        self.v2.resultado_final = Validacion.CONFORME
        self.v2.corregida = True
        self.v2.save()
        _, _, filas = self.descargar(q="Ana", estado="corregidas")
        fila = filas[0]
        self.assertEqual((fila["resultado_modelo"], fila["resultado_final"], fila["corregida"]), ("No cumple", "Cumple", "Sí"))
        self.assertEqual(fila["epp_Guantes"], "Detectado (corregido)")

    # HU11-CA03 / RNF06: sin hash del QR y con la cédula enmascarada
    def test_no_incluye_qr_ni_cedula_completa(self):
        _, texto, filas = self.descargar()
        self.assertNotIn("A1" * 32, texto)
        self.assertNotIn("qr", texto.lower())
        self.assertNotIn("0911111111", texto)
        self.assertIn("09••••••11", {f["cedula"] for f in filas})

    def test_texto_que_parece_formula_se_neutraliza(self):
        _, _, filas = self.descargar(q="Mora")
        self.assertTrue(filas[0]["estudiante"].startswith("'="))

    # RF10-CA04: botón deshabilitado sin resultados
    def test_boton_en_pantalla(self):
        self.assertContains(self.client.get(reverse("historial:registros")), "Exportar CSV (3)")
        self.assertContains(self.client.get(reverse("historial:incidencias")), "Exportar CSV (2)")
        vacia = self.client.get(reverse("historial:registros"), {"q": "nadie"})
        self.assertContains(vacia, 'aria-disabled="true" title="No hay registros para exportar"')

    def test_no_aparece_en_la_pestana_de_reincidentes(self):
        respuesta = self.client.get(reverse("historial:incidencias"), {"tab": "reincidentes"})
        self.assertNotContains(respuesta, "Exportar CSV")

    def test_consulta_vacia_devuelve_solo_encabezados(self):
        _, _, filas = self.descargar(q="nadie")
        self.assertEqual(filas, [])

    # Acceso
    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("historial:registros_csv")).status_code, 302)
