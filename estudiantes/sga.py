"""Consulta de los datos públicos del carné en la página de validación del SGA de la UNEMI.

Uso autorizado para el estudio de caso. Solo se leen los datos necesarios
(nombres, carrera, facultad, modalidad, nivel y vigencia); la foto y la cédula
NO se guardan (RNF06). Si la consulta falla, el carné queda "Pendiente de
revisión" y la verificación continúa normalmente (RNF10).
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from configuracion.models import Parametro

PREFIJO_POR_DEFECTO = "https://sga.unemi.edu.ec/p_valida_carnet/"
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
CONECTORES = {"de", "del", "la", "las", "los", "y"}


@dataclass
class DatosSGA:
    valido: bool
    nombres: str | None = None
    apellidos: str | None = None
    carrera: str | None = None
    facultad: str | None = None
    modalidad: str | None = None
    nivel: str | None = None
    inicio_vigencia: date | None = None
    fin_vigencia: date | None = None


def url_validacion(codigo):
    prefijo = Parametro.obtener("prefijo_qr_valido", PREFIJO_POR_DEFECTO)
    return f"{prefijo}digital?code={codigo}"


def consultar(codigo):
    """Descarga la página de validación y devuelve DatosSGA, o None si no se pudo consultar."""
    try:
        respuesta = requests.get(
            url_validacion(codigo),
            timeout=getattr(settings, "SGA_TIEMPO_ESPERA", 3),
            headers={"User-Agent": "VerificacionEPP-UNEMI/1.0 (prototipo académico)"},
        )
        respuesta.raise_for_status()
    except requests.RequestException:
        return None
    return interpretar(respuesta.text)


# ---------------------------------------------------------------- lectura del HTML

def _normalizar(texto):
    """Mayúsculas, sin tildes y con espacios simples, para comparar etiquetas."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def _lineas(html):
    soup = BeautifulSoup(html, "html.parser")
    for etiqueta in soup(["script", "style", "noscript"]):
        etiqueta.decompose()
    return [linea.strip() for linea in soup.get_text("\n").splitlines() if linea.strip()]


def _valor(lineas, etiqueta):
    """Devuelve el texto que sigue a una etiqueta como 'CARRERA' (en la línea siguiente o en la misma)."""
    for i, linea in enumerate(lineas):
        normal = _normalizar(linea)
        if normal == etiqueta and i + 1 < len(lineas):
            return lineas[i + 1].strip()
        if normal.startswith(etiqueta + " ") or normal.startswith(etiqueta + ":"):
            return linea[len(etiqueta):].lstrip(" :").strip() or None
    return None


def _fechas(texto):
    resultado = []
    for dia, mes, anio in re.findall(r"(\d{1,2})\s+de\s+([a-záéíóúA-ZÁÉÍÓÚ]+)\s+de\s+(\d{4})", texto or ""):
        numero_mes = MESES.get(_normalizar(mes).lower())
        if numero_mes:
            try:
                resultado.append(date(int(anio), numero_mes, int(dia)))
            except ValueError:
                pass
    return resultado


def _formato_nombre(texto):
    palabras = texto.lower().split()
    return " ".join(p if (p in CONECTORES and i > 0) else p.capitalize() for i, p in enumerate(palabras))


def _nombre(lineas):
    """El nombre aparece en mayúsculas justo antes de 'ESTUDIANTE UNEMI' (en una o dos líneas)."""
    normales = [_normalizar(l) for l in lineas]
    if "ESTUDIANTE UNEMI" not in normales:
        return None, None
    i = normales.index("ESTUDIANTE UNEMI")
    candidatas = []
    for linea in reversed(lineas[max(0, i - 2):i]):
        if re.fullmatch(r"[A-ZÁÉÍÓÚÑÜ ]{3,}", linea.strip()):
            candidatas.insert(0, linea.strip())
        else:
            break
    if len(candidatas) == 2:
        return _formato_nombre(candidatas[0]), _formato_nombre(candidatas[1])
    if len(candidatas) == 1:
        partes = candidatas[0].split()
        if len(partes) >= 3:  # convención: los dos últimos son los apellidos
            return _formato_nombre(" ".join(partes[:-2])), _formato_nombre(" ".join(partes[-2:]))
        return _formato_nombre(candidatas[0]), None
    return None, None


def interpretar(html):
    lineas = _lineas(html)
    texto = _normalizar(" ".join(lineas))
    valido = "CARNE VALIDO" in texto and "NO VALIDO" not in texto and "INVALIDO" not in texto
    nombres, apellidos = _nombre(lineas)
    if not valido and not nombres:
        return DatosSGA(valido=False)
    vigencia = _fechas(_valor(lineas, "VIGENCIA") or "")
    return DatosSGA(
        valido=valido,
        nombres=nombres,
        apellidos=apellidos,
        carrera=_valor(lineas, "CARRERA"),
        facultad=_valor(lineas, "FACULTAD"),
        modalidad=_valor(lineas, "MODALIDAD"),
        nivel=_valor(lineas, "NIVEL"),
        inicio_vigencia=vigencia[0] if len(vigencia) >= 1 else None,
        fin_vigencia=vigencia[1] if len(vigencia) >= 2 else None,
    )
