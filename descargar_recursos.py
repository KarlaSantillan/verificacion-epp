"""Descarga una sola vez las librerías y fuentes que hoy se cargan desde internet
(Bootstrap, Bootstrap Icons, fuente Inter y html5-qrcode) y las guarda en static/vendor/.

Uso (desde la carpeta del proyecto, con el entorno virtual activo):
    python descargar_recursos.py

Así las páginas cargan más rápido, sin "saltos" de fuente ni íconos, y el aplicativo
funciona aunque no haya internet (por ejemplo, en la sustentación).
"""
import re
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent / "static" / "vendor"
CDN = "https://cdn.jsdelivr.net/npm"
ARCHIVOS = {
    "bootstrap/bootstrap.min.css": f"{CDN}/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    "bootstrap/bootstrap.bundle.min.js": f"{CDN}/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
    "bootstrap-icons/bootstrap-icons.min.css": f"{CDN}/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    "bootstrap-icons/fonts/bootstrap-icons.woff2": f"{CDN}/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2",
    "bootstrap-icons/fonts/bootstrap-icons.woff": f"{CDN}/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff",
    "html5-qrcode/html5-qrcode.min.js": f"{CDN}/html5-qrcode@2.3.8/html5-qrcode.min.js",
    "chartjs/chart.umd.min.js": f"{CDN}/chart.js@4.4.4/dist/chart.umd.min.js",
}
PESOS = (400, 500, 600, 700)
for peso in PESOS:
    ARCHIVOS[f"inter/inter-latin-{peso}-normal.woff2"] = f"{CDN}/@fontsource/inter@5.1.0/files/inter-latin-{peso}-normal.woff2"


def descargar(url, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        datos = respuesta.read()
    if len(datos) < 500:
        raise ValueError(f"respuesta demasiado pequeña ({len(datos)} bytes)")
    destino.write_bytes(datos)
    return len(datos)


errores = 0
for ruta, url in ARCHIVOS.items():
    try:
        tam = descargar(url, BASE / ruta)
        print(f"  OK  {ruta}  ({tam // 1024} KB)")
    except Exception as error:  # noqa: BLE001
        errores += 1
        print(f"  ERROR  {ruta}: {error}")

# Bootstrap Icons pide la fuente con "?<hash>"; se quita para que coincida con la precarga.
css_iconos = BASE / "bootstrap-icons" / "bootstrap-icons.min.css"
if css_iconos.exists():
    texto = css_iconos.read_text(encoding="utf-8")
    css_iconos.write_text(re.sub(r'(bootstrap-icons\.woff2?)\?[^")]*', r"\1", texto), encoding="utf-8")

# Hoja de estilos de la fuente Inter (solo latín: incluye tildes y ñ).
reglas = [
    "@font-face {\n"
    "  font-family: \"Inter\";\n"
    "  font-style: normal;\n"
    f"  font-weight: {peso};\n"
    "  font-display: swap;\n"
    f"  src: url(\"inter-latin-{peso}-normal.woff2\") format(\"woff2\");\n"
    "}"
    for peso in PESOS
]
(BASE / "inter").mkdir(parents=True, exist_ok=True)
(BASE / "inter" / "inter.css").write_text("\n".join(reglas) + "\n", encoding="utf-8")
print("  OK  inter/inter.css")

if errores:
    print(f"\nTerminó con {errores} error(es). Revise su conexión a internet y vuelva a ejecutarlo.")
    sys.exit(1)
print("\nListo: todo quedó en static/vendor/. Ahora haga los cambios de INSTRUCCIONES.txt.")
