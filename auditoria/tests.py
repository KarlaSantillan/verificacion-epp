"""Pruebas de TK08 (auditoría automática) y HU17 (consulta de la auditoría).

Ejecutar con:  python manage.py test auditoria
"""
import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from auditoria.contexto import como_sistema, fijar_usuario, restaurar_usuario
from auditoria.models import Auditoria
from configuracion.models import Epp, Laboratorio, LaboratorioEpp
from estudiantes.models import Estudiante
from usuarios.models import Rol, Usuario

CLAVE = "ClaveSegura-2026"


class AuditoriaAutomaticaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rol_admin = Rol.objects.create(nombre=Rol.ADMINISTRADOR)
        cls.rol_docente = Rol.objects.create(nombre=Rol.DOCENTE)
        cls.admin = Usuario.objects.create_user("admin@prueba.ec", CLAVE, nombres="Ada", apellidos="Admin", rol=cls.rol_admin)
        Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Dora", apellidos="Docente", rol=cls.rol_docente)
        cls.bata = Epp.objects.create(nombre="Bata", clase_modelo="lab_coat")
        cls.lab = Laboratorio.objects.create(nombre="Lab A", tiempo_estabilizacion_segundos=3)
        cls.requisito = LaboratorioEpp.objects.create(laboratorio=cls.lab, epp=cls.bata, confianza_minima=Decimal("0.80"))

    def setUp(self):
        self.client.login(username="admin@prueba.ec", password=CLAVE)

    def ultimo(self, tabla):
        return Auditoria.objects.filter(tabla_afectada=tabla).order_by("-id_auditoria").first()

    # --- TK08-CA01: inserción, modificación y desactivación
    def test_insercion_desde_la_pantalla_registra_al_usuario(self):
        self.client.post(reverse("administracion:epp_nuevo"), {"nombre": "Botas", "clase_modelo": "boots", "activo": "on"})
        evento = self.ultimo("epp_m_epp")
        self.assertEqual(evento.accion, "INSERT")
        self.assertEqual(evento.usuario, self.admin)
        self.assertEqual(evento.tipo_actor, Auditoria.USUARIO)
        self.assertEqual(evento.datos_nuevos["clase_modelo"], "boots")

    def test_modificacion_guarda_solo_lo_que_cambio_con_antes_y_despues(self):
        datos = {"lab-nombre": "Lab A", "lab-tiempo_estabilizacion_segundos": 3, "lab-activo": "on",
                 f"req-obl_{self.bata.id_epp}": "on", f"req-conf_{self.bata.id_epp}": 85}
        self.client.post(reverse("administracion:laboratorio_editar", args=[self.lab.pk]), datos)
        evento = self.ultimo("epp_m_laboratorio_epp")
        self.assertEqual(evento.accion, "UPDATE")
        self.assertEqual(evento.datos_anteriores, {"confianza_minima": 0.8})
        self.assertEqual(evento.datos_nuevos, {"confianza_minima": 0.85})

    def test_desactivar_se_registra_como_desactivacion(self):
        self.client.post(reverse("administracion:cambiar_activo", args=["epp", self.bata.pk]))
        evento = self.ultimo("epp_m_epp")
        self.assertEqual(evento.accion, "DELETE")
        self.assertEqual(evento.datos_nuevos, {"activo": False})

    def test_guardar_sin_cambios_no_crea_evento(self):
        antes = Auditoria.objects.count()
        self.lab.save()
        self.assertEqual(Auditoria.objects.count(), antes)

    # --- Datos sensibles (RNF06)
    def test_la_contrasena_nunca_se_guarda(self):
        self.client.post(reverse("administracion:usuario_nuevo"), {
            "nombres": "Nuevo", "apellidos": "Docente", "correo": "nuevo@prueba.ec", "rol": self.rol_docente.pk,
            "activo": "on", "contrasena": "OtraClave-2026", "confirmacion": "OtraClave-2026"})
        evento = self.ultimo("epp_m_usuario")
        texto = json.dumps(evento.datos_nuevos)
        self.assertNotIn("password", texto)
        self.assertNotIn("pbkdf2", texto)
        usuario = Usuario.objects.get(correo="nuevo@prueba.ec")
        usuario.set_password("Cambiada-2026")
        usuario.save()
        evento = self.ultimo("epp_m_usuario")
        self.assertEqual(evento.datos_nuevos, {"contrasena": "cambiada"})

    def test_la_cedula_se_guarda_enmascarada(self):
        Estudiante.objects.create(nombres="Ana", cedula="0912345678")
        evento = self.ultimo("epp_m_estudiante")
        self.assertEqual(evento.datos_nuevos["cedula"], "09••••••78")

    # --- TK08-CA02: actor Sistema
    def test_sin_sesion_el_actor_es_sistema(self):
        Epp.objects.create(nombre="Casco", clase_modelo="helmet")
        evento = self.ultimo("epp_m_epp")
        self.assertEqual(evento.tipo_actor, Auditoria.SISTEMA)
        self.assertIsNone(evento.usuario)

    def test_como_sistema_aunque_haya_usuario(self):
        token = fijar_usuario(self.admin)
        try:
            with como_sistema():
                Epp.objects.create(nombre="Delantal", clase_modelo="apron")
        finally:
            restaurar_usuario(token)
        self.assertEqual(self.ultimo("epp_m_epp").tipo_actor, Auditoria.SISTEMA)

    # --- HU17: consulta
    def test_hu17_ca03_solo_el_administrador_consulta(self):
        self.assertEqual(self.client.get(reverse("administracion:auditoria")).status_code, 200)
        self.client.logout()
        self.client.login(username="docente@prueba.ec", password=CLAVE)
        self.assertEqual(self.client.get(reverse("administracion:auditoria")).status_code, 403)

    def test_hu17_ca01_filtros(self):
        self.client.post(reverse("administracion:cambiar_activo", args=["epp", self.bata.pk]))
        respuesta = self.client.get(reverse("administracion:auditoria"), {"accion": "DELETE", "tabla": "epp_m_epp"})
        eventos = list(respuesta.context["pagina"])
        self.assertTrue(eventos)
        self.assertTrue(all(e.accion == "DELETE" and e.tabla_afectada == "epp_m_epp" for e in eventos))
        respuesta = self.client.get(reverse("administracion:auditoria"), {"usuario": self.admin.pk, "actor": "usuario"})
        self.assertTrue(all(e.usuario_id == self.admin.pk for e in respuesta.context["pagina"]))

    def test_hu17_detalle_explica_el_cambio(self):
        self.client.post(reverse("administracion:cambiar_activo", args=["epp", self.bata.pk]))
        evento = self.ultimo("epp_m_epp")
        respuesta = self.client.get(reverse("administracion:auditoria_detalle", args=[evento.pk]))
        self.assertContains(respuesta, "Estado cambió de «Activo» a «Inactivo».")

    def test_hu17_ca02_no_se_puede_modificar(self):
        evento = Auditoria.objects.first()
        self.assertEqual(self.client.post(reverse("administracion:auditoria_detalle", args=[evento.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("administracion:auditoria")).status_code, 405)
