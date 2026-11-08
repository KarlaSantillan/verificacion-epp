"""Pruebas de HU10 (historial e incidencias) y HU09 (corrección manual).

Ejecutar con:  python manage.py test historial
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import Auditoria
from configuracion.models import Epp, Laboratorio, ModeloVision, PeriodoAcademico
from estudiantes.models import CarnetEstudiantil, Estudiante
from usuarios.models import Rol, Usuario
from verificacion.models import CorreccionValidacion, Validacion, ValidacionDetalle

CLAVE = "ClaveSegura-2026"


def momento(dia):
    return timezone.make_aware(datetime(2026, 11, dia, 10, 0))


class HistorialTests(TestCase):
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
        cls.ana = cls.crear_carnet("Ana", "Pérez", "0911111111", "A1")
        cls.luis = cls.crear_carnet("Luis", "Mora", "0922222222", "B2")
        # Ana: cumple (lab A, día 3) · no cumple sin guantes (lab A, día 5) · no cumple (lab B, día 5)
        cls.v1 = cls.crear_validacion(cls.ana, cls.lab_a, 3, guantes=True)
        cls.v2 = cls.crear_validacion(cls.ana, cls.lab_a, 5, guantes=False)
        cls.v3 = cls.crear_validacion(cls.luis, cls.lab_b, 5, guantes=False)

    @classmethod
    def crear_carnet(cls, nombres, apellidos, cedula, codigo):
        estudiante = Estudiante.objects.create(nombres=nombres, apellidos=apellidos, cedula=cedula)
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
        for epp, detectado, confianza in [(cls.bata, True, "0.90"), (cls.guantes, guantes, "0.90" if guantes else "0.40")]:
            ValidacionDetalle.objects.create(
                validacion=validacion, epp=epp, requerido=True, detectado_modelo=detectado, detectado_final=detectado,
                confianza=Decimal(confianza), umbral_usado=Decimal("0.80"),
            )
        return validacion

    def setUp(self):
        self.client.login(username="docente@prueba.ec", password=CLAVE)

    def ids(self, nombre, **filtros):
        respuesta = self.client.get(reverse(f"historial:{nombre}"), filtros)
        return {v.pk for v in respuesta.context["pagina"]}

    # --- HU10
    def test_cp29_filtros_combinados(self):
        filtros = {"laboratorio": self.lab_a.pk, "desde": "2026-11-04", "hasta": "2026-11-06", "estado": "no_conforme"}
        self.assertEqual(self.ids("registros", **filtros), {self.v2.pk})

    def test_cp30_busqueda_por_cedula_y_nombre(self):
        self.assertEqual(self.ids("registros", q="0911111111"), {self.v1.pk, self.v2.pk})
        self.assertEqual(self.ids("registros", q="mora"), {self.v3.pk})

    def test_cp31_incidencias_solo_no_cumple(self):
        self.assertEqual(self.ids("incidencias"), {self.v2.pk, self.v3.pk})
        self.assertEqual(self.ids("incidencias", estado="conforme"), {self.v2.pk, self.v3.pk})  # el filtro de estado no aplica

    def test_sin_resultados_muestra_limpiar_filtros(self):
        respuesta = self.client.get(reverse("historial:registros"), {"q": "nadie"})
        self.assertContains(respuesta, "Sin registros")
        self.assertContains(respuesta, "Limpiar filtros")

    def test_detalle_muestra_epp_y_faltantes(self):
        respuesta = self.client.get(reverse("historial:detalle", args=[self.v2.pk]))
        self.assertContains(respuesta, "Guantes")
        self.assertContains(respuesta, "Corregir detección")
        lista = self.client.get(reverse("historial:registros"), {"q": "Mora"})
        self.assertContains(lista, "Guantes")  # columna Faltantes

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("historial:registros")).status_code, 302)

    # --- HU09
    def url_corregir(self, validacion, epp):
        detalle = validacion.detalles.get(epp=epp)
        return reverse("historial:corregir", args=[validacion.pk, detalle.pk]), detalle

    def test_cp27_falso_negativo_recalcula_y_conserva_el_modelo(self):
        url, detalle = self.url_corregir(self.v2, self.guantes)
        self.client.post(url, {"valor_nuevo": "1", "observacion": "Usaba guantes transparentes."})
        self.v2.refresh_from_db()
        detalle.refresh_from_db()
        self.assertEqual(self.v2.resultado_final, Validacion.CONFORME)
        self.assertEqual(self.v2.resultado_modelo, Validacion.NO_CONFORME)  # CA03
        self.assertTrue(self.v2.corregida)
        self.assertTrue(detalle.detectado_final)
        self.assertFalse(detalle.detectado_modelo)
        correccion = CorreccionValidacion.objects.get()
        self.assertEqual(correccion.tipo_error, CorreccionValidacion.FALSO_NEGATIVO)
        self.assertEqual((correccion.valor_anterior, correccion.valor_nuevo), (False, True))
        self.assertEqual(correccion.usuario, self.docente)
        self.assertTrue(Auditoria.objects.filter(tabla_afectada="epp_p_correccion_validacion", usuario=self.docente).exists())
        self.assertNotIn(self.v2.pk, self.ids("incidencias"))  # ya no es incidencia

    def test_cp28_sin_observacion_no_se_guarda(self):
        url, detalle = self.url_corregir(self.v2, self.guantes)
        respuesta = self.client.post(url, {"valor_nuevo": "1", "observacion": "   "})
        self.assertContains(respuesta, "La observación es obligatoria")
        self.assertFalse(CorreccionValidacion.objects.exists())
        self.v2.refresh_from_db()
        self.assertFalse(self.v2.corregida)

    def test_falso_positivo_cambia_a_no_cumple(self):
        url, _ = self.url_corregir(self.v1, self.bata)
        self.client.post(url, {"valor_nuevo": "0", "observacion": "Era una camisa blanca, no una bata."})
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.resultado_final, Validacion.NO_CONFORME)
        self.assertEqual(CorreccionValidacion.objects.get().tipo_error, CorreccionValidacion.FALSO_POSITIVO)

    def test_valor_igual_al_actual_no_se_guarda(self):
        url, _ = self.url_corregir(self.v1, self.bata)
        respuesta = self.client.post(url, {"valor_nuevo": "1", "observacion": "Sin cambio"})
        self.assertContains(respuesta, "igual al actual")
        self.assertFalse(CorreccionValidacion.objects.exists())

    def test_detalle_de_otra_validacion_da_404(self):
        detalle = self.v1.detalles.first()
        self.assertEqual(self.client.get(reverse("historial:corregir", args=[self.v2.pk, detalle.pk])).status_code, 404)
