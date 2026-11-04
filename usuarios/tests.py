"""Pruebas de HU01 – Inicio de sesión según rol.

Ejecutar con:  python manage.py test usuarios
"""
from django.test import TestCase
from django.urls import reverse

from auditoria.models import Auditoria
from usuarios.models import Rol, Usuario

CLAVE = "ClaveSegura-2026"


class InicioSesionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol_docente = Rol.objects.create(nombre=Rol.DOCENTE)
        rol_admin = Rol.objects.create(nombre=Rol.ADMINISTRADOR)
        cls.docente = Usuario.objects.create_user("docente@prueba.ec", CLAVE, nombres="Ana", apellidos="Prueba", rol=rol_docente)
        cls.admin = Usuario.objects.create_user("admin@prueba.ec", CLAVE, nombres="Luis", apellidos="Prueba", rol=rol_admin)
        cls.inactivo = Usuario.objects.create_user(
            "inactivo@prueba.ec", CLAVE, nombres="Eva", apellidos="Prueba", rol=rol_docente, activo=False
        )

    def ingresar(self, correo, clave=CLAVE):
        return self.client.post(reverse("usuarios:login"), {"username": correo, "password": clave})

    def test_cp01_docente_accede_y_solo_ve_el_menu_de_operacion(self):
        respuesta = self.ingresar("docente@prueba.ec")
        self.assertRedirects(respuesta, reverse("core:inicio"))
        inicio = self.client.get(reverse("core:inicio"))
        self.assertContains(inicio, 'id="menu-operacion"')
        self.assertNotContains(inicio, 'id="menu-administracion"')

    def test_administrador_ve_el_menu_de_administracion(self):
        self.ingresar("admin@prueba.ec")
        inicio = self.client.get(reverse("core:inicio"))
        self.assertContains(inicio, 'id="menu-administracion"')

    def test_cp02_contrasena_incorrecta_muestra_mensaje_generico(self):
        respuesta = self.ingresar("docente@prueba.ec", "otra-clave")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Correo o contraseña incorrectos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cp03_usuario_desactivado_no_puede_ingresar(self):
        respuesta = self.ingresar("inactivo@prueba.ec")
        self.assertContains(respuesta, "Correo o contraseña incorrectos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cp04_docente_no_accede_a_paginas_de_administracion(self):
        self.ingresar("docente@prueba.ec")
        self.assertEqual(self.client.get(reverse("core:administracion")).status_code, 403)
        # El panel de Django tampoco lo deja pasar: lo envía a su propio inicio de sesión.
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_administrador_accede_a_administracion(self):
        self.ingresar("admin@prueba.ec")
        self.assertEqual(self.client.get(reverse("core:administracion")).status_code, 200)

    def test_usuario_sin_sesion_es_enviado_al_inicio_de_sesion(self):
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertRedirects(respuesta, f"{reverse('usuarios:login')}?next={reverse('core:inicio')}")

    def test_rf01_ca05_el_inicio_de_sesion_queda_en_la_auditoria(self):
        self.ingresar("docente@prueba.ec")
        evento = Auditoria.objects.get(accion="LOGIN")
        self.assertEqual(evento.usuario, self.docente)
        self.assertEqual(evento.tipo_actor, Auditoria.USUARIO)

    def test_cierre_de_sesion(self):
        self.ingresar("docente@prueba.ec")
        self.client.post(reverse("usuarios:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
