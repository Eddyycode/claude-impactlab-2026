"""
Orquesta la evaluación completa de una dirección:
    geocode → [crime, air, seismic, flood, water] en paralelo + transit
    → normaliza a 1–10 → devuelve reportData completo.

Exponemos `compute_location_score(direccion, mcp)` como la tool que Claude
llama cuando quiere una evaluación integral.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from tools.geocode import geocode_address
from tools.scoring import (
    score_air,
    score_crime,
    score_flood,
    score_seismic,
    score_water,
)
from tools.transit import get_transit_access


async def _mcp_call_safe(mcp, name: str, args: dict) -> str:
    """Wrapper que nunca levanta — devuelve '' si falla."""
    try:
        return await mcp.call_tool(name, args)
    except Exception as e:
        print(f"[report_builder] tool {name} failed: {e}")
        return ""


def _etiqueta(score: float) -> str:
    if score >= 8.5: return "Excelente"
    if score >= 7.0: return "Bueno"
    if score >= 5.5: return "Aceptable"
    if score >= 4.0: return "Preocupante"
    return "Evitar"


async def compute_location_score(direccion: str, mcp) -> dict:
    """Devuelve el reportData completo o un dict con error si geocode falla."""
    geo = geocode_address(direccion)
    if not geo:
        return {
            "__error__": "geocode_failed",
            "direccion": direccion,
        }

    # Nominatim devuelve p.ej. "Cuauhtémoc". Atlas/agua guardan así (acento+título).
    # FGJ guarda "CUAUHTEMOC" (mayúsculas sin acento). Mantenemos ambas formas.
    alcaldia_original = geo.get("alcaldia") or "Cuauhtémoc"
    colonia = geo.get("colonia") or ""

    # FGJ usa UPPERCASE sin acentos → "CUAUHTEMOC"
    alc_upper_unaccent = (
        alcaldia_original.upper()
        .replace("Á", "A").replace("É", "E").replace("Í", "I")
        .replace("Ó", "O").replace("Ú", "U")
    )

    # Atlas usa Title Case CON acentos. ILIKE en PG no ignora acentos,
    # así que usamos PREFIJO (primeras 5 chars) para matchear sin necesidad de acentos.
    # "Cuauh" matchea "Cuauhtémoc"; "Benit" matchea "Benito Juárez", etc.
    alc_prefix = alcaldia_original[:5]

    # Evaluar las 5 tools de CKAN + 1 de Supabase EN PARALELO
    # cdmx-mcp normaliza identificadores — mandamos SIN comillas, solo literales con '
    results = await asyncio.gather(
        _mcp_call_safe(mcp, "crime_hotspots", {
            "year": 2024, "alcaldia": alc_upper_unaccent, "top_n": 50
        }),
        _mcp_call_safe(mcp, "air_quality_now", {"limit": 10}),
        _mcp_call_safe(mcp, "query_records", {
            "dataset_id": "atlas-de-riesgo-sismico",
            "where": f"alcaldia ILIKE '{alc_prefix}%'",
            "limit": 50,
        }),
        _mcp_call_safe(mcp, "query_records", {
            "dataset_id": "atlas-de-riesgo-inundaciones",
            "where": f"alcaldia ILIKE '{alc_prefix}%'",
            "limit": 50,
        }),
        _mcp_call_safe(mcp, "query_records", {
            "dataset_id": "reportes-de-agua",
            "where": (
                f"colonia_catalogo ILIKE '%{colonia.upper()}%'"
                if colonia else
                f"alcaldia_catalogo ILIKE '{alcaldia_original.upper()[:5]}%'"
            ),
            "limit": 500,
        }),
    )

    crime_raw, air_raw, seismic_raw, flood_raw, water_raw = results

    # Normalizar a dimensiones 1–10
    dims = [
        score_crime(crime_raw, alcaldia_original),
        score_air(air_raw),
        score_seismic(seismic_raw, alcaldia_original),
        score_flood(flood_raw, alcaldia_original),
        score_water(water_raw, alcaldia_original),
    ]

    # Transporte via Supabase (sync por ahora — ya es rápido)
    faltantes = []
    try:
        transit = get_transit_access(geo["lat"], geo["lng"], radio_m=800)
        dims.append({
            "id": "transporte",
            "nombre": "Transporte Público",
            "score": transit["score"],
            "peso_aplicado": 14,
            "fuente": "GTFS CDMX",
            "dataset_id": "gtfs-cdmx-supabase",
            "consultado_en": dims[0]["consultado_en"],
            "dato_bruto": transit["dato_bruto"],
            "detalle": transit["detalle"],
        })
    except Exception as e:
        faltantes.append({"id": "transporte", "razon": f"Supabase error: {e}"})

    # Renormalizar pesos si hay faltantes
    active_weight = sum(d["peso_aplicado"] for d in dims)
    target = 100
    if active_weight > 0 and active_weight != target:
        for d in dims:
            d["peso_aplicado"] = round(d["peso_aplicado"] * target / active_weight, 1)

    # Score global ponderado
    total_w = sum(d["peso_aplicado"] for d in dims)
    global_score = round(
        sum(d["score"] * d["peso_aplicado"] for d in dims) / total_w, 1
    ) if total_w else 0.0

    # Dimensiones cosméticas: ecobici/servicios/integridad (no las evaluamos en MVP)
    faltantes.extend([
        {"id": "ecobici", "razon": "ECOBICI no conectado en MVP"},
        {"id": "servicios", "razon": "DENUE (INEGI) requiere token, no conectado"},
        {"id": "integridad_2017", "razon": "Cálculo point-in-polygon pendiente"},
    ])

    return {
        "direccion": geo["direccion"],
        "lat": geo["lat"],
        "lng": geo["lng"],
        "scores": {
            "global": global_score,
            "etiqueta_global": _etiqueta(global_score),
            "dimensiones": dims,
            "faltantes": faltantes,
        },
        "resumen": "",   # lo llena el narrator después
    }
