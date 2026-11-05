"""Pruebas de las pantallas de administración (HU12 y HU13).

Ejecutar con:  python manage.py test administracion
"""
import tempfile
from decimal import Decimal
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from configuracion.models import Epp, Laboratorio, LaboratorioEpp, ModeloVision, Parametro, PeriodoAcademico
from usuarios.models import Rol, Usuario

CLAVE = "ClaveSegura-2026"


class AdministracionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rol_admin = Rol.objects.create(nombre=Rol.ADMINISTRADOR)
        cls.rol_docente = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.admin = Usuario.objects.create_user("admin@prueba.ec", CLAVE, nombres="Ada", apellidos="Admin", rol=cls.rol_admin)
        Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=cls.rol_docente)
        cls.bata = Epp.objects.create(nombre="Bata", clase_modelo="lab_coat")
        cls.guantes = Epp.objects.create(nombre="Guantes", clase_modelo="gloves")
        cls.lab = Laboratorio.objects.create(nombre="Lab A", tiempo_estabilizacion_segundos=3)

    def setUp(self):
        self.client.login(username="admin@prueba.ec", password=CLAVE)

    # --- Acceso (RNF02)
    def test_docente_no_entra_a_administracion(self):
        self.client.logout()
        self.client.login(username="docente@prueba.ec", password=CLAVE)
        for nombre in ["laboratorios", "catalogo", "estudiantes", "usuarios", "periodos", "parametros", "modelos"]:
            self.assertEqual(self.client.get(reverse(f"administracion:{nombre}")).status_code, 403, nombre)

    def test_administrador_ve_todas_las_pantallas(self):
        for nombre in ["laboratorios", "catalogo", "estudiantes", "usuarios", "periodos", "parametros", "modelos"]:
            self.assertEqual(self.client.get(reverse(f"administracion:{nombre}")).status_code, 200, nombre)
        self.assertEqual(self.client.get(reverse("administracion:estudiantes") + "?tab=carnes").status_code, 200)

    # --- Laboratorios (HU12)
    def datos_lab(self, **requisitos):
        datos = {"lab-nombre": "Lab A", "lab-ubicacion": "", "lab-descripcion": "", "lab-tiempo_estabilizacion_segundos": 3, "lab-activo": "on"}
        for epp in (self.bata, self.guantes):
            datos[f"req-conf_{epp.id_epp}"] = 80
        datos.update(requisitos)
        return datos

    def test_hu12_guarda_requisitos_y_obligatorio_implica_habilitado(self):
        url = reverse("administracion:laboratorio_editar", args=[self.lab.pk])
        self.client.post(url, self.datos_lab(**{f"req-obl_{self.bata.id_epp}": "on", f"req-conf_{self.bata.id_epp}": 85}))
        requisito = LaboratorioEpp.objects.get(laboratorio=self.lab, epp=self.bata)
        self.assertTrue(requisito.activo and requisito.obligatorio)
        self.assertEqual(requisito.confianza_minima, Decimal("0.85"))
        self.assertFalse(LaboratorioEpp.objects.filter(laboratorio=self.lab, epp=self.guantes).exists())

    def test_hu12_ca02_confianza_fuera_de_rango_se_rechaza(self):
        url = reverse("administracion:laboratorio_editar", args=[self.lab.pk])
        respuesta = self.client.post(url, self.datos_lab(**{f"req-obl_{self.bata.id_epp}": "on", f"req-conf_{self.bata.id_epp}": 150}))
        self.assertContains(respuesta, "Debe estar entre 1 y 100.")
        self.assertFalse(LaboratorioEpp.objects.exists())

    def test_hu12_estabilizacion_entre_1_y_10(self):
        url = reverse("administracion:laboratorio_editar", args=[self.lab.pk])
        respuesta = self.client.post(url, self.datos_lab(**{"lab-tiempo_estabilizacion_segundos": 0}))
        self.assertContains(respuesta, "Debe estar entre 1 y 10 segundos.")

    def test_laboratorio_sin_obligatorios_muestra_advertencia(self):
        url = reverse("administracion:laboratorio_editar", args=[self.lab.pk])
        respuesta = self.client.post(url, self.datos_lab(), follow=True)
        self.assertContains(respuesta, "no podrá usarse en la verificación")

    def test_crear_laboratorio(self):
        self.client.post(reverse("administracion:laboratorio_nuevo"), self.datos_lab(**{"lab-nombre": "Lab C", f"req-obl_{self.guantes.id_epp}": "on"}))
        nuevo = Laboratorio.objects.get(nombre="Lab C")
        self.assertEqual(nuevo.requisitos.count(), 1)

    # --- Usuarios (HU13-CA02)
    def datos_usuario(self, **extra):
        datos = {"nombres": "Nuevo", "apellidos": "Docente", "correo": "nuevo@prueba.ec", "rol": self.rol_docente.pk, "activo": "on",
                 "contrasena": "OtraClave-2026", "confirmacion": "OtraClave-2026"}
        datos.update(extra)
        return datos

    def test_crear_usuario_con_contrasena_cifrada(self):
        self.client.post(reverse("administracion:usuario_nuevo"), self.datos_usuario())
        usuario = Usuario.objects.get(correo="nuevo@prueba.ec")
        self.assertTrue(usuario.check_password("OtraClave-2026"))
        self.assertNotEqual(usuario.password, "OtraClave-2026")

    def test_hu13_ca02_correo_repetido_se_rechaza(self):
        respuesta = self.client.post(reverse("administracion:usuario_nuevo"), self.datos_usuario(correo="DOCENTE@prueba.ec"))
        self.assertContains(respuesta, "Ya existe un usuario con ese correo.")

    def test_contrasenas_distintas_se_rechazan(self):
        respuesta = self.client.post(reverse("administracion:usuario_nuevo"), self.datos_usuario(confirmacion="otra"))
        self.assertContains(respuesta, "Las contraseñas no coinciden.")

    def test_no_puede_desactivarse_a_si_mismo(self):
        self.client.post(reverse("administracion:cambiar_activo", args=["usuario", self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.activo)

    # --- Activar / desactivar (HU13-CA01)
    def test_hu13_ca01_desactivar_no_elimina(self):
        self.client.post(reverse("administracion:cambiar_activo", args=["epp", self.guantes.pk]))
        self.guantes.refresh_from_db()
        self.assertFalse(self.guantes.activo)
        self.client.post(reverse("administracion:cambiar_activo", args=["epp", self.guantes.pk]))
        self.guantes.refresh_from_db()
        self.assertTrue(self.guantes.activo)

    def test_tipo_desconocido_404(self):
        self.assertEqual(self.client.post(reverse("administracion:cambiar_activo", args=["rol", 1])).status_code, 404)

    # --- Catálogo
    def test_clase_del_modelo_con_formato(self):
        respuesta = self.client.post(reverse("administracion:epp_nuevo"), {"nombre": "Botas", "clase_modelo": "Botas Seguridad", "activo": "on"})
        self.assertContains(respuesta, "Use solo minúsculas")

    # --- Periodos (RF15-CA04)
    def test_periodo_con_fin_antes_del_inicio_se_rechaza(self):
        respuesta = self.client.post(reverse("administracion:periodos"), {"nombre": "Malo", "fecha_inicio": "2026-12-01", "fecha_fin": "2026-08-01"})
        self.assertContains(respuesta, "La fecha de fin debe ser posterior al inicio.")
        self.assertFalse(PeriodoAcademico.objects.exists())

    # --- Parámetros (HU13-CA04)
    def test_hu13_ca04_umbral_de_incidencias_entre_1_y_20(self):
        parametro = Parametro.objects.create(clave="umbral_incidencias", valor="3")
        url = reverse("administracion:parametro_editar", args=[parametro.pk])
        for malo in ("25", "0", "2.5", "abc"):
            self.assertContains(self.client.post(url, {"valor": malo}), "Debe ser un número entero entre 1 y 20.")
            parametro.refresh_from_db()
            self.assertEqual(parametro.valor, "3")
        self.client.post(url, {"valor": "5"})
        parametro.refresh_from_db()
        self.assertEqual(parametro.valor, "5")

    def test_prefijo_qr_debe_ser_https(self):
        parametro = Parametro.objects.create(clave="prefijo_qr_valido", valor="https://sga.unemi.edu.ec/p_valida_carnet/")
        self.client.post(reverse("administracion:parametro_editar", args=[parametro.pk]), {"valor": "http://otro.com/"})
        parametro.refresh_from_db()
        self.assertEqual(parametro.valor, "https://sga.unemi.edu.ec/p_valida_carnet/")

    # --- Modelo de visión (HU13-CA03)
    def test_hu13_ca03_solo_un_modelo_activo(self):
        with tempfile.TemporaryDirectory() as carpeta, override_settings(MODELOS_DIR=carpeta):
            for version in ("v1", "v2"):
                Path(carpeta, f"epp_{version}.pt").write_bytes(b"x")
            v1 = ModeloVision.objects.create(nombre="epp", version="v1", activo=True)
            v2 = ModeloVision.objects.create(nombre="epp", version="v2")
            self.client.post(reverse("administracion:modelo_activar", args=[v2.pk]))
            v1.refresh_from_db()
            v2.refresh_from_db()
            self.assertTrue(v2.activo)
            self.assertFalse(v1.activo)

    def test_no_se_activa_un_modelo_sin_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta, override_settings(MODELOS_DIR=carpeta):
            v3 = ModeloVision.objects.create(nombre="epp", version="v3")
            self.client.post(reverse("administracion:modelo_activar", args=[v3.pk]))
            v3.refresh_from_db()
            self.assertFalse(v3.activo)
