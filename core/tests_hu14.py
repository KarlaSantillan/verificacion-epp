"""Pruebas de HU14: dashboard de indicadores (RF11 – CP33 y CP34).

Ejecutar con:  python manage.py test core
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from configuracion.models import Epp, Laboratorio, ModeloVision, PeriodoAcademico
from core import indicadores
from estudiantes.models import CarnetEstudiantil, Estudiante
from usuarios.models import Rol, Usuario
from verificacion.models import Validacion, ValidacionDetalle

CLAVE = "ClaveSegura-2026"
C, N = Validacion.CONFORME, Validacion.NO_CONFORME


class DashboardIndicadoresTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            "docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=Rol.objects.create(nombre=Rol.DOCENTE)
        )
        cls.admin = Usuario.objects.create_user(
            "admin@prueba.ec", CLAVE, nombres="Ada", apellidos="Admin", rol=Rol.objects.create(nombre=Rol.ADMINISTRADOR)
        )
        cls.lab_a = Laboratorio.objects.create(nombre="Lab A")
        cls.lab_b = Laboratorio.objects.create(nombre="Lab B")
        cls.bata = Epp.objects.create(nombre="Bata", clase_modelo="lab_coat")
        cls.guantes = Epp.objects.create(nombre="Guantes", clase_modelo="gloves")
        cls.gafas = Epp.objects.create(nombre="Gafas", clase_modelo="safety_glasses")
        hoy = timezone.localdate()
        cls.actual = PeriodoAcademico.objects.create(nombre="Actual", fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy + timedelta(days=30))
        cls.anterior = PeriodoAcademico.objects.create(nombre="Anterior", fecha_inicio=hoy - timedelta(days=200), fecha_fin=hoy - timedelta(days=61))
        cls.modelo = ModeloVision.objects.create(nombre="epp-yolov8", version="v1", activo=True)
        cls.carnet = CarnetEstudiantil.objects.create(
            usuario_registro=cls.docente, estudiante=Estudiante.objects.create(nombres="Ana", apellidos="Pérez"),
            qr_hash="a" * 64, codigo_validacion="TEST0001", estado_registro=CarnetEstudiantil.REGISTRADO,
        )

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def validar(self, final, lab=None, periodo=None, dias_atras=0, modelo=None, faltan=(), corregida=False):
        """Crea una validación. `faltan` = EPP requeridos que quedaron como no detectados (detectado_final=False)."""
        validacion = Validacion.objects.create(
            usuario_supervisor=self.docente, periodo=periodo or self.actual, modelo=self.modelo, carnet=self.carnet,
            laboratorio=lab or self.lab_a, fecha_hora=timezone.now() - timedelta(days=dias_atras),
            resultado_modelo=modelo or final, resultado_final=final, corregida=corregida,
        )
        for epp in (self.bata, self.guantes, self.gafas):
            detectado = epp not in faltan
            ValidacionDetalle.objects.create(
                validacion=validacion, epp=epp, requerido=True, detectado_modelo=detectado, detectado_final=detectado,
                confianza=Decimal("0.9") if detectado else Decimal("0.2"), umbral_usado=Decimal("0.80"),
            )
        return validacion

    def ver(self, **parametros):
        respuesta = self.client.get(reverse("core:inicio"), parametros)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.context

    # CA01 (CP33)
    def test_cp33_porcentaje_coincide_con_calculo_manual(self):
        for _ in range(5):
            self.validar(C)
        for _ in range(3):
            self.validar(N, faltan=[self.guantes])
        resumen = self.ver()["resumen"]
        self.assertEqual(resumen["total"], 8)
        self.assertEqual(resumen["conformes"], 5)
        self.assertEqual(resumen["no_conformes"], 3)
        self.assertEqual(resumen["porcentaje"], 62.5)  # 5 / 8 × 100

    def test_porcentaje_con_decimales_periodicos(self):
        self.validar(C)
        self.validar(N, faltan=[self.bata])
        self.validar(N, faltan=[self.bata])
        self.assertEqual(self.ver()["resumen"]["porcentaje"], 33.3)  # 1 / 3 × 100 = 33,33…

    def test_sin_validaciones_no_muestra_cero_por_ciento(self):
        contexto = self.ver()
        self.assertEqual(contexto["resumen"]["total"], 0)
        self.assertIsNone(contexto["resumen"]["porcentaje"])
        self.assertContains(self.client.get(reverse("core:inicio")), "No hay validaciones registradas")

    # CA02 (CP34)
    def test_cp34_cambia_al_filtrar_por_laboratorio(self):
        self.validar(C, lab=self.lab_a)
        self.validar(N, lab=self.lab_b, faltan=[self.gafas])
        self.validar(N, lab=self.lab_b, faltan=[self.gafas])
        self.assertEqual(self.ver()["resumen"]["total"], 3)
        self.assertEqual(self.ver(laboratorio=self.lab_a.pk)["resumen"]["porcentaje"], 100.0)
        self.assertEqual(self.ver(laboratorio=self.lab_b.pk)["resumen"]["porcentaje"], 0.0)

    def test_cp34_cambia_al_filtrar_por_periodo(self):
        self.validar(C)
        self.validar(N, periodo=self.anterior, dias_atras=100, faltan=[self.bata])
        actual = self.ver()  # por defecto, el periodo vigente
        self.assertEqual(actual["periodo"], self.actual)
        self.assertEqual(actual["resumen"]["total"], 1)
        anterior = self.ver(periodo=self.anterior.pk)["resumen"]
        self.assertEqual((anterior["total"], anterior["no_conformes"]), (1, 1))

    def test_comparacion_por_laboratorio_solo_con_todos(self):
        self.validar(C, lab=self.lab_a)
        self.validar(N, lab=self.lab_b, faltan=[self.bata])
        filas = {f["nombre"]: f["porcentaje"] for f in self.ver()["por_laboratorio"]}
        self.assertEqual(filas, {"Lab A": 100.0, "Lab B": 0.0})
        self.assertEqual(self.ver(laboratorio=self.lab_a.pk)["por_laboratorio"], [])

    # CA03
    def test_ca03_usa_el_resultado_final_corregido(self):
        # El modelo dijo "No cumple", pero el docente lo corrigió a "Cumple" (HU09).
        self.validar(C, modelo=N, corregida=True)
        resumen = self.ver()["resumen"]
        self.assertEqual((resumen["conformes"], resumen["no_conformes"], resumen["corregidas"]), (1, 0, 1))

    def test_ca03_epp_faltante_usa_detectado_final(self):
        validacion = self.validar(N, faltan=[self.guantes, self.gafas])
        # El docente corrigió las gafas: sí las llevaba (falso negativo).
        detalle = validacion.detalles.get(epp=self.gafas)
        detalle.detectado_final = True
        detalle.save()
        self.validar(N, faltan=[self.guantes])
        faltantes = self.ver()["faltantes"]
        self.assertEqual(faltantes, [{"nombre": "Guantes", "veces": 2, "porcentaje": 100.0}])

    def test_epp_mas_faltante_ordenado(self):
        self.validar(N, faltan=[self.gafas])
        self.validar(N, faltan=[self.gafas, self.bata])
        self.validar(N, faltan=[self.gafas])
        self.validar(C)
        nombres = [f["nombre"] for f in self.ver()["faltantes"]]
        self.assertEqual(nombres, ["Gafas", "Bata"])

    # Gráfico
    def test_serie_por_dia_y_por_semana(self):
        self.validar(C, dias_atras=0)
        self.validar(N, dias_atras=0, faltan=[self.bata])
        self.validar(C, dias_atras=2)
        contexto = self.ver()
        self.assertEqual(contexto["agrupacion"], "dia")  # 2 días de datos
        self.assertEqual(sum(p["total"] for p in contexto["serie"]), 3)
        self.assertEqual(len(contexto["serie"]), 2)  # los días sin validaciones no aparecen
        self.validar(C, dias_atras=30)
        self.assertEqual(self.ver()["agrupacion"], "semana")  # más de 14 días de datos
        self.assertEqual(self.ver(agrupar="dia")["agrupacion"], "dia")  # el usuario puede cambiarlo

    def test_suma_de_la_serie_coincide_con_el_total(self):
        for dias in (0, 1, 1, 5, 9, 20, 40):
            self.validar(C if dias % 2 else N, dias_atras=dias, faltan=[] if dias % 2 else [self.bata])
        contexto = self.ver(agrupar="semana")
        self.assertEqual(sum(p["total"] for p in contexto["serie"]), contexto["resumen"]["total"])
        self.assertEqual(sum(p["conformes"] for p in contexto["serie"]), contexto["resumen"]["conformes"])

    # Acceso y robustez
    def test_docente_y_administrador_lo_ven(self):
        self.validar(C)
        self.assertContains(self.client.get(reverse("core:inicio")), "Cumplimiento de EPP en el tiempo")
        self.client.login(username="admin@prueba.ec", password=CLAVE)
        self.assertContains(self.client.get(reverse("core:inicio")), "Cumplimiento de EPP en el tiempo")

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("core:inicio")).status_code, 302)

    def test_parametros_invalidos_no_rompen_la_pagina(self):
        contexto = self.ver(periodo="abc", laboratorio="9999", agrupar="mes")
        self.assertEqual(contexto["periodo"], self.actual)
        self.assertIsNone(contexto["laboratorio"])


class FuncionesIndicadoresTests(TestCase):
    def test_porcentaje(self):
        self.assertIsNone(indicadores.porcentaje(0, 0))
        self.assertEqual(indicadores.porcentaje(2, 3), 66.7)
        self.assertEqual(indicadores.porcentaje(9, 10), 90.0)

    def test_nivel_de_color(self):
        self.assertEqual(indicadores.nivel(90), "alto")
        self.assertEqual(indicadores.nivel(89.9), "medio")
        self.assertEqual(indicadores.nivel(70), "medio")
        self.assertEqual(indicadores.nivel(69.9), "bajo")
        self.assertEqual(indicadores.nivel(None), "sin-datos")
