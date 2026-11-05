"""Servicio de detección de EPP en tiempo real (TK07 / RF05, RNF03, RNF10).

Recibe un fotograma (JPEG) de la cámara, ejecuta el modelo YOLOv8 activo y
devuelve los EPP detectados con su clase, confianza y posición.

- El modelo se carga una sola vez y queda en memoria (cargar un .pt tarda segundos).
- El archivo del modelo se busca en  modelos/epp_<versión>.pt  (ej.: modelos/epp_v1.pt),
  según la versión del modelo marcado como activo en el panel.
- Los fotogramas se procesan en memoria y NO se guardan (TK07-CA03, RF05-CA05).
"""
import threading
import time
from pathlib import Path

from django.conf import settings

from configuracion.models import ModeloVision


class DeteccionNoDisponible(Exception):
    """El servicio no puede detectar (sin modelo activo, archivo faltante, etc.)."""


class ImagenNoValida(Exception):
    """El fotograma recibido no es una imagen válida."""


# Un solo modelo en memoria. El candado evita que dos peticiones usen el modelo a la vez.
_candado = threading.RLock()
_cache = {"id": None, "modelo": None, "nombre": None}


def _imgsz():
    return int(getattr(settings, "DETECCION_IMGSZ", 640))


def _confianza_base():
    # Umbral bajo y general: el umbral de cada EPP por laboratorio se aplica después (HU07).
    return float(getattr(settings, "DETECCION_CONFIANZA", 0.25))


def ruta_modelo(modelo):
    carpeta = Path(getattr(settings, "MODELOS_DIR", Path(settings.BASE_DIR) / "modelos"))
    return carpeta / f"epp_{modelo.version}.pt"


def obtener_modelo():
    """Devuelve (modelo YOLO, nombre). Lo recarga solo si cambió el modelo activo."""
    activo = ModeloVision.objects.filter(activo=True).first()
    if activo is None:
        raise DeteccionNoDisponible("No hay un modelo de visión activo. Regístrelo en el panel de administración.")
    with _candado:
        if _cache["id"] != activo.pk:
            ruta = ruta_modelo(activo)
            if not ruta.exists():
                raise DeteccionNoDisponible(f"No se encontró el archivo del modelo: modelos/{ruta.name}")
            try:
                import numpy as np
                from ultralytics import YOLO
            except ImportError as error:
                raise DeteccionNoDisponible("Falta instalar la librería ultralytics.") from error
            yolo = YOLO(str(ruta))
            # Primera predicción "en vacío": la primera siempre es lenta.
            yolo.predict(np.zeros((_imgsz(), _imgsz(), 3), dtype=np.uint8), imgsz=_imgsz(), verbose=False)
            _cache.update(id=activo.pk, modelo=yolo, nombre=str(activo))
        return _cache["modelo"], _cache["nombre"]


def decodificar(datos):
    """Convierte los bytes del JPEG en una imagen de OpenCV (en memoria, sin guardar)."""
    import cv2
    import numpy as np

    imagen = cv2.imdecode(np.frombuffer(datos or b"", dtype=np.uint8), cv2.IMREAD_COLOR) if datos else None
    if imagen is None:
        raise ImagenNoValida("El fotograma recibido no es una imagen válida.")
    return imagen


def detectar(datos):
    """Analiza un fotograma y devuelve las detecciones (TK07-CA02).

    Respuesta:
      {"detecciones": [{"clase": "gloves", "confianza": 0.91, "caja": [x1, y1, x2, y2]}, ...],
       "ms": 85, "modelo": "epp-yolov8n v1"}
    La caja va en proporciones de 0 a 1 respecto al ancho y alto de la imagen,
    así la interfaz la puede dibujar sobre el video sin importar su tamaño.
    """
    modelo, nombre = obtener_modelo()  # primero: si no hay modelo, error controlado (CA04)
    imagen = decodificar(datos)
    with _candado:
        inicio = time.perf_counter()
        resultado = modelo.predict(imagen, imgsz=_imgsz(), conf=_confianza_base(), verbose=False)[0]
        ms = round((time.perf_counter() - inicio) * 1000)

    cajas = resultado.boxes
    detecciones = [
        {
            "clase": resultado.names[int(clase)],
            "confianza": round(float(confianza), 3),
            "caja": [round(float(v), 4) for v in caja],
        }
        for caja, confianza, clase in zip(cajas.xyxyn.tolist(), cajas.conf.tolist(), cajas.cls.tolist())
    ]
    return {"detecciones": detecciones, "ms": ms, "modelo": nombre}
