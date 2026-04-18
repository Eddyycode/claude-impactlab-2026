"""
Geocodificación con Nominatim (OpenStreetMap).

API pública sin token — con política:
- User-Agent descriptivo (obligatorio)
- Max 1 req/s — cacheamos respuestas para no abusar.

Devuelve:
    {
        "lat": float,
        "lng": float,
        "direccion": str,       # texto legible completo
        "alcaldia": str | None,
        "colonia": str | None,
    }

O None si Nominatim no encontró match.
"""

from __future__ import annotations

from typing import Optional

import httpx

# Cache manual (no lru_cache) para poder saltarnos los None y reintentar.
_CACHE: dict[str, dict] = {}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "colonia-cdmx-hackathon/0.1 (hackathon ImpactLab CDMX)"

ALCALDIAS_CDMX = {
    "Álvaro Obregón", "Azcapotzalco", "Benito Juárez", "Coyoacán",
    "Cuajimalpa de Morelos", "Cuauhtémoc", "Gustavo A. Madero",
    "Iztacalco", "Iztapalapa", "Magdalena Contreras", "Miguel Hidalgo",
    "Milpa Alta", "Tláhuac", "Tlalpan", "Venustiano Carranza", "Xochimilco",
}


def _normalize_query(q: str) -> str:
    # Añadir "Ciudad de México" si no aparece, para sesgar el match.
    q = q.strip()
    low = q.lower()
    if "cdmx" in low or "ciudad de méxico" in low or "ciudad de mexico" in low:
        return q
    return f"{q}, Ciudad de México, México"


def _geocode_cached(query: str) -> Optional[dict]:
    if query in _CACHE:
        return _CACHE[query]
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "mx",
    }
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "es"}
    try:
        resp = httpx.get(NOMINATIM_URL, params=params, headers=headers, timeout=10.0)
        resp.raise_for_status()
        hits = resp.json()
    except Exception as e:
        print(f"[geocode] error: {e}")
        return None

    if not hits:
        return None

    h = hits[0]
    addr = h.get("address", {}) or {}
    alcaldia = (
        addr.get("borough")
        or addr.get("city_district")
        or addr.get("suburb")
        or addr.get("municipality")
    )
    # Normalizar al catálogo CDMX si hay match parcial
    if alcaldia:
        for canonical in ALCALDIAS_CDMX:
            if canonical.lower() in alcaldia.lower() or alcaldia.lower() in canonical.lower():
                alcaldia = canonical
                break

    colonia = (
        addr.get("neighbourhood")
        or addr.get("quarter")
        or addr.get("suburb")
    )

    result = {
        "lat": float(h["lat"]),
        "lng": float(h["lon"]),
        "direccion": h.get("display_name", query),
        "alcaldia": alcaldia,
        "colonia": colonia,
    }
    _CACHE[query] = result
    return result


def geocode_address(text: str) -> Optional[dict]:
    """Geocodifica texto libre a coords CDMX. Devuelve None si no hay match."""
    if not text or not text.strip():
        return None
    return _geocode_cached(_normalize_query(text))
