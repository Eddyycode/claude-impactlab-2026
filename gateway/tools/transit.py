"""
Acceso a transporte público via Supabase PostGIS.

Llama la función `stations_within_radius(lat, lng, radius_m)` ya creada en
Supabase (ver `data_ingestion/setup_schema.sql`).

Devuelve:
    {
        "count": int,
        "estaciones": [{"nombre","modo","linea","distancia_m"}, ...],
        "score": float,         # 1.0–10.0 según ponderación por modo
        "dato_bruto": str,      # frase para UI ("14 paradas RTP en 800 m")
    }

Fórmula de score (de PROPUESTA.md §"Las 9 dimensiones" #6):
    peso_por_modo = {metro: 3, metrobus: 2, rtp/trolebus/cablebus: 1}
    score_raw = Σ (peso × conteo_por_modo)
    score = min(score_raw, 10.0)

Si la lista está vacía: score = 1.0 (piso).
"""

from __future__ import annotations

import os
from typing import Optional

from supabase import Client, create_client

_client: Optional[Client] = None

_MODE_WEIGHT = {
    "metro": 3.0,
    "metrobus": 2.0,
    "trolebus": 1.0,
    "cablebus": 1.0,
    "rtp": 1.0,
    "bus": 1.0,
}


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        # Anon key es suficiente: hay policy SELECT abierta para anon sobre la tabla.
        key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL y SUPABASE_ANON_KEY deben estar en .env")
        _client = create_client(url, key)
    return _client


def get_transit_access(lat: float, lng: float, radio_m: int = 800) -> dict:
    sb = _get_client()
    resp = sb.rpc(
        "stations_within_radius",
        {"lat": lat, "lng": lng, "radius_m": radio_m},
    ).execute()
    rows = resp.data or []

    # Frecuencia por modo + score ponderado
    by_mode: dict[str, int] = {}
    for r in rows:
        m = (r.get("modo") or "bus").lower()
        by_mode[m] = by_mode.get(m, 0) + 1

    score_raw = sum(_MODE_WEIGHT.get(m, 1.0) * n for m, n in by_mode.items())
    score = max(1.0, min(score_raw, 10.0))

    estaciones = [
        {
            "nombre": r.get("nombre"),
            "modo": r.get("modo"),
            "linea": r.get("linea"),
            "distancia_m": round(float(r.get("distancia_m") or 0)),
        }
        for r in rows
    ]

    # Frase legible — prioriza el modo más fuerte presente
    if not rows:
        dato_bruto = f"Sin estaciones en {radio_m} m"
        detalle = "Zona con baja cobertura de transporte público estructurado"
    else:
        partes = []
        if by_mode.get("metro"):
            partes.append(f"{by_mode['metro']} Metro")
        if by_mode.get("metrobus"):
            partes.append(f"{by_mode['metrobus']} Metrobús")
        if by_mode.get("trolebus"):
            partes.append(f"{by_mode['trolebus']} Trolebús")
        if by_mode.get("cablebus"):
            partes.append(f"{by_mode['cablebus']} Cablebús")
        if by_mode.get("rtp"):
            partes.append(f"{by_mode['rtp']} RTP")
        dato_bruto = " · ".join(partes) + f" en {radio_m} m"
        detalle = (
            f"Estación más cercana: {rows[0].get('nombre')} "
            f"({round(float(rows[0].get('distancia_m') or 0))} m)"
        )

    return {
        "count": len(rows),
        "estaciones": estaciones,
        "score": round(score, 1),
        "dato_bruto": dato_bruto,
        "detalle": detalle,
    }
