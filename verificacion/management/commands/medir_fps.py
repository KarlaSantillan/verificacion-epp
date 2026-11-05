"""Mide la velocidad del servicio de detección (TK07-CA01 / RNF03: al menos 5 FPS).

Uso:
    python manage.py medir_fps                    (usa la cámara web, 50 fotogramas)
    python manage.py medir_fps --n 100
    python manage.py medir_fps --imagen foto.jpg  (repite una misma imagen)

Ninguna imagen se guarda: los fotogramas se procesan en memoria.
"""
import platform
import statistics
import time

from django.core.management.base import BaseCommand, CommandError

from verificacion import deteccion


class Command(BaseCommand):
    help = "Mide los fotogramas por segundo del servicio de detección de EPP."

    def add_arguments(self, parser):
        parser.add_argument("--n", type=int, default=50, help="Cantidad de fotogramas a medir.")
        parser.add_argument("--imagen", help="Ruta de una imagen de prueba (si no se indica, usa la cámara).")
        parser.add_argument("--camara", type=int, default=0, help="Número de la cámara (por defecto 0).")

    def handle(self, *args, **opciones):
        import cv2

        try:
            _, nombre = deteccion.obtener_modelo()
        except deteccion.DeteccionNoDisponible as error:
            raise CommandError(str(error))

        if opciones["imagen"]:
            imagen = cv2.imread(opciones["imagen"])
            if imagen is None:
                raise CommandError("No se pudo abrir la imagen.")
            fotogramas = lambda: imagen  # noqa: E731
            camara = None
        else:
            camara = cv2.VideoCapture(opciones["camara"])
            if not camara.isOpened():
                raise CommandError("No se pudo abrir la cámara.")

            def fotogramas():
                ok, cuadro = camara.read()
                if not ok:
                    raise CommandError("La cámara dejó de enviar imágenes.")
                return cuadro

        self.stdout.write(f"Modelo: {nombre}  |  imgsz: {deteccion._imgsz()}  |  fotogramas: {opciones['n']}")
        tiempos, ultimo, por_clase = [], None, {}
        try:
            for _ in range(opciones["n"]):
                # Se codifica a JPEG como lo hará el navegador, para medir el camino real.
                _, jpeg = cv2.imencode(".jpg", fotogramas(), [cv2.IMWRITE_JPEG_QUALITY, 80])
                inicio = time.perf_counter()
                ultimo = deteccion.detectar(jpeg.tobytes())
                tiempos.append((time.perf_counter() - inicio) * 1000)
                for d in ultimo["detecciones"]:
                    por_clase.setdefault(d["clase"], []).append(d["confianza"])
        finally:
            if camara is not None:
                camara.release()

        promedio = statistics.mean(tiempos)
        fps = 1000 / promedio
        self.stdout.write("")
        self.stdout.write(f"Equipo: {platform.system()} {platform.release()} | {platform.processor() or platform.machine()}")
        self.stdout.write(f"Tiempo por fotograma: promedio {promedio:.0f} ms | mínimo {min(tiempos):.0f} ms | máximo {max(tiempos):.0f} ms")
        estilo = self.style.SUCCESS if fps >= 5 else self.style.ERROR
        self.stdout.write(estilo(f"Velocidad: {fps:.1f} FPS  ({'cumple' if fps >= 5 else 'NO cumple'} el mínimo de 5 FPS)"))
        if ultimo and ultimo["detecciones"]:
            clases = ", ".join(f"{d['clase']} {d['confianza']:.2f}" for d in ultimo["detecciones"])
            self.stdout.write(f"Último fotograma: {clases}")
        self.stdout.write("\nDetecciones por clase (fotogramas | confianza promedio | máxima):")
        for clase, valores in sorted(por_clase.items()):
            self.stdout.write(f"  {clase:15} {len(valores):3}/{opciones['n']} | {statistics.mean(valores):.2f} | {max(valores):.2f}")