"""Prueba la lectura de la página de validación del SGA con un carné real.

Uso:
    python manage.py consultar_sga 2744921411013
    python manage.py consultar_sga 2744921411013 --guardar    (guarda el HTML en sga_pagina.html)

Muestra solo en la consola lo que el sistema lograría leer. No guarda nada en la base de datos.
"""
import requests
from django.core.management.base import BaseCommand

from estudiantes import sga


class Command(BaseCommand):
    help = "Consulta la página de validación del SGA y muestra los datos que el sistema puede leer."

    def add_arguments(self, parser):
        parser.add_argument("codigo", help="Código de validación impreso en el carné")
        parser.add_argument("--guardar", action="store_true", help="Guarda el HTML recibido en sga_pagina.html")

    def handle(self, *args, codigo, guardar, **options):
        url = sga.url_validacion(codigo)
        self.stdout.write(f"Consultando: {url}")
        try:
            respuesta = requests.get(url, timeout=10, headers={"User-Agent": "VerificacionEPP-UNEMI/1.0 (prototipo académico)"})
        except requests.RequestException as error:
            self.stderr.write(self.style.ERROR(f"No se pudo conectar: {error}"))
            return
        self.stdout.write(f"Código HTTP: {respuesta.status_code} · Tamaño: {len(respuesta.text)} caracteres · Tiempo: {respuesta.elapsed.total_seconds():.2f} s")
        if guardar:
            with open("sga_pagina.html", "w", encoding="utf-8") as archivo:
                archivo.write(respuesta.text)
            self.stdout.write("HTML guardado en sga_pagina.html (no lo suba al repositorio: contiene datos personales).")
        datos = sga.interpretar(respuesta.text)
        for campo, valor in vars(datos).items():
            self.stdout.write(f"  {campo:16} {valor}")
        if datos.valido and not datos.nombres:
            self.stdout.write(self.style.WARNING("La página dice que el carné es válido, pero no se pudo leer el nombre: hay que ajustar sga.py."))
