"""
Normalizadores — convierten el output crudo de cada tool a score 1–10
+ dato_bruto (frase) + detalle (frase de contexto).

Fórmulas tomadas de PROPUESTA.md §"Las 9 dimensiones".
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

TODAY = datetime.now().strftime("%Y-%m-%d")


def _clamp(x: float, lo: float = 1.0, hi: float = 10.0) -> float:
    return round(max(lo, min(hi, x)), 1)


# ──────────── Seguridad (crimen · FGJ vía cdmx-mcp crime_hotspots) ────────────
def score_crime(raw_json: str, alcaldia: str) -> dict:
    """
    `raw_json` es lo que devolvió cdmx-mcp — JSON con shape {preview:[...], total_count:N}.
    Cada row tiene `colonia_hecho` y `delitos` (count). Sumamos para total alcaldía.
    """
    total = 0
    top_colonia = None
    try:
        data = _parse_json(raw_json)
        rows = data.get("preview", data.get("results", [])) if isinstance(data, dict) else data
        if isinstance(rows, list):
            for r in rows:
                n = r.get("delitos", r.get("total", r.get("count", 0))) or 0
                total += int(n)
            if rows:
                top = max(rows, key=lambda x: x.get("delitos", 0) or 0)
                top_colonia = top.get("colonia_hecho")
    except Exception:
        total = 0

    # Heurística para top-N colonias de la alcaldía:
    # con top_n=50 cubrimos ~90% del crimen de la alcaldía.
    if total == 0:
        score = 5.0
    elif total < 3000:
        score = 9.0
    elif total < 8000:
        score = 7.5
    elif total < 20000:
        score = 6.0
    elif total < 40000:
        score = 4.5
    else:
        score = 3.0

    dato = f"{total:,} delitos en {alcaldia} (top colonias)" if total else f"Sin datos FGJ para {alcaldia}"
    det = _crime_detalle(total)
    if top_colonia and total:
        det = f"Colonia con más delitos: {top_colonia}"

    return {
        "id": "seguridad",
        "nombre": "Seguridad",
        "score": _clamp(score),
        "peso_aplicado": 20,
        "fuente": "FGJ CDMX — carpetas de investigación",
        "dataset_id": "fgj",
        "consultado_en": TODAY,
        "dato_bruto": dato,
        "detalle": det,
    }


def _crime_detalle(total: int) -> str:
    if total == 0:
        return "Datos FGJ no disponibles para esta alcaldía"
    if total < 15000:
        return "Por debajo de la mediana de CDMX"
    if total < 30000:
        return "Nivel medio — comparable al promedio CDMX"
    return "Por encima del promedio de CDMX"


# ──────────── Calidad del aire (SIMAT vía air_quality_now) ────────────
def score_air(raw_json: str) -> dict:
    # Detección rápida de error upstream (CKAN 409)
    if not raw_json or "Error executing tool" in raw_json or "409" in raw_json:
        return {
            "id": "aire", "nombre": "Calidad del Aire",
            "score": 5.0, "peso_aplicado": 12,
            "fuente": "SIMAT — estaciones SEDEMA",
            "dataset_id": "aire", "consultado_en": TODAY,
            "dato_bruto": "SIMAT sin datos hoy (upstream 409)",
            "detalle": "El feed de CKAN SIMAT respondió con error; no se pudo medir PM2.5",
        }
    try:
        data = _parse_json(raw_json)
        rows = data.get("preview", data.get("results", [])) if isinstance(data, dict) else data
        values = []
        if isinstance(rows, list):
            for r in rows:
                v = (r.get("pm25") or r.get("PM25") or r.get("valor") or
                     r.get("pm_25") or r.get("pm2_5"))
                if v is not None:
                    try: values.append(float(v))
                    except (ValueError, TypeError): pass
        pm25 = sum(values) / len(values) if values else None
    except Exception:
        pm25 = None

    if pm25 is None:
        score = 5.0
        dato_bruto = "Sin lectura reciente de PM2.5"
        detalle = "SIMAT no devolvió datos disponibles"
    else:
        # OMS: <12 excelente, 25 medio, >55 malo
        if pm25 <= 12:
            score = 10.0
        elif pm25 <= 25:
            score = 10.0 - ((pm25 - 12) / 13) * 5.0  # 10 → 5
        elif pm25 <= 55:
            score = 5.0 - ((pm25 - 25) / 30) * 4.0   # 5 → 1
        else:
            score = 1.0
        dato_bruto = f"PM2.5 ≈ {pm25:.0f} µg/m³"
        if pm25 <= 12:
            detalle = "Dentro del rango OMS"
        elif pm25 <= 25:
            detalle = "Ligeramente arriba del límite OMS"
        else:
            detalle = "Por encima de la recomendación OMS"

    return {
        "id": "aire",
        "nombre": "Calidad del Aire",
        "score": _clamp(score),
        "peso_aplicado": 12,
        "fuente": "SIMAT — estaciones SEDEMA",
        "dataset_id": "aire",
        "consultado_en": TODAY,
        "dato_bruto": dato_bruto,
        "detalle": detalle,
    }


# ──────────── Riesgo sísmico · query_records("atlas-de-riesgo-sismico") ────────────
def score_seismic(raw_json: str, alcaldia: str) -> dict:
    try:
        data = _parse_json(raw_json)
        rows = data.get("preview", data.get("results", [])) if isinstance(data, dict) else data
        if isinstance(rows, list) and rows:
            intensidades = [str(r.get("intensidad", "")).lower() for r in rows]
            # mayor intensidad = peor score
            has_alto = any("alto" in i for i in intensidades)
            has_medio = any("medio" in i for i in intensidades)
            if has_alto:
                score, txt = 3.5, "Riesgo alto — zona de suelos blandos"
            elif has_medio:
                score, txt = 6.0, "Riesgo medio — zona de transición"
            else:
                score, txt = 8.0, "Riesgo bajo — zona firme"
            dato_bruto = f"{len(rows)} polígonos de riesgo en {alcaldia}"
        else:
            score, txt = 5.0, "Sin polígonos de riesgo registrados"
            dato_bruto = f"Sin datos sísmicos para {alcaldia}"
    except Exception:
        score, txt = 5.0, "Error procesando Atlas de Riesgo"
        dato_bruto = "No se pudo evaluar"

    return {
        "id": "sismico",
        "nombre": "Riesgo sísmico",
        "score": _clamp(score),
        "peso_aplicado": 18,
        "fuente": "Atlas de Riesgo CDMX — Sísmico",
        "dataset_id": "atlas-de-riesgo-sismico",
        "consultado_en": TODAY,
        "dato_bruto": dato_bruto,
        "detalle": txt,
    }


# ──────────── Riesgo de inundación ────────────
def score_flood(raw_json: str, alcaldia: str) -> dict:
    try:
        data = _parse_json(raw_json)
        rows = data.get("preview", data.get("results", [])) if isinstance(data, dict) else data
        if isinstance(rows, list) and rows:
            intensidades = [str(r.get("intensidad", "")).lower() for r in rows]
            has_muyalto = any("muy alto" in i or "critico" in i for i in intensidades)
            has_alto = any("alto" in i and "muy alto" not in i for i in intensidades)
            has_medio = any("medio" in i for i in intensidades)
            if has_muyalto:
                score, txt = 2.0, "Riesgo muy alto — zonas con encharcamientos críticos"
            elif has_alto:
                score, txt = 4.5, "Riesgo alto — encharcamientos recurrentes"
            elif has_medio:
                score, txt = 7.0, "Riesgo medio — encharcamientos ocasionales"
            else:
                score, txt = 9.0, "Riesgo bajo — drenaje adecuado"
            dato_bruto = f"{len(rows)} polígonos de inundación en {alcaldia}"
        else:
            score, txt = 8.0, "Sin registros de inundación significativa"
            dato_bruto = f"Sin polígonos de inundación en {alcaldia}"
    except Exception:
        score, txt = 5.0, "Error procesando Atlas de Riesgo"
        dato_bruto = "No se pudo evaluar"

    return {
        "id": "inundacion",
        "nombre": "Riesgo de inundación",
        "score": _clamp(score),
        "peso_aplicado": 8,
        "fuente": "Atlas de Riesgo CDMX — Inundaciones",
        "dataset_id": "atlas-de-riesgo-inundaciones",
        "consultado_en": TODAY,
        "dato_bruto": dato_bruto,
        "detalle": txt,
    }


# ──────────── Confiabilidad del agua (SACMEX — reportes recientes) ────────────
def score_water(raw_json: str, alcaldia: str) -> dict:
    try:
        data = _parse_json(raw_json)
        rows = data.get("preview", data.get("results", [])) if isinstance(data, dict) else data
        count = len(rows) if isinstance(rows, list) else 0
    except Exception:
        count = 0

    # Heurística: <50 reportes/6m/colonia = bueno, >500 = malo
    if count == 0:
        score, txt = 5.0, "Sin reportes recientes (o dato no disponible)"
    elif count < 50:
        score, txt = 8.5, "Pocos reportes — suministro confiable"
    elif count < 150:
        score, txt = 7.0, "Reportes moderados — servicio estable con fluctuaciones"
    elif count < 400:
        score, txt = 5.0, "Reportes frecuentes — fluctuaciones recurrentes"
    else:
        score, txt = 3.0, "Muchos reportes — fallas de suministro frecuentes"

    return {
        "id": "agua",
        "nombre": "Confiabilidad del Agua",
        "score": _clamp(score),
        "peso_aplicado": 14,
        "fuente": "SACMEX — Reportes de agua 2022-2024",
        "dataset_id": "reportes-de-agua",
        "consultado_en": TODAY,
        "dato_bruto": f"{count} reportes registrados (últimos meses)",
        "detalle": txt,
    }


# ──────────── helpers ────────────
def _parse_json(raw: str):
    """cdmx-mcp puede devolver JSON plano o texto con trozos. Intentamos parsear."""
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Intentar extraer el primer bloque {...} o [...]
        m = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return []
