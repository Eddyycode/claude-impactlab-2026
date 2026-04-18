"""
load_gtfs_stops.py — carga stops.txt (GTFS) a Supabase.

Uso:
    python data_ingestion/load_gtfs_stops.py

Requisitos:
    pip install supabase python-dotenv
    Variables .env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

STOPS_FILE = Path(__file__).parent / "raw" / "stops.txt"
BATCH_SIZE = 500

# Inferencia de modo por prefijo de stop_id.
# Si más adelante se agregan feeds de Metro/Metrobús, extender este mapa.
MODE_PREFIX = {
    "M": "metro",
    "MB": "metrobus",
    "TR": "trolebus",
    "CB": "cablebus",
    "B": "rtp",  # autobuses RTP (el feed actual)
}


def infer_mode(stop_id: str) -> str:
    prefix = stop_id.split("_", 1)[0] if "_" in stop_id else stop_id[:2]
    return MODE_PREFIX.get(prefix, "bus")


def read_stops() -> list[dict]:
    rows: list[dict] = []
    with STOPS_FILE.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                lat = float(r["stop_lat"])
                lng = float(r["stop_lon"])
            except (KeyError, ValueError):
                continue
            rows.append({
                "stop_id": r["stop_id"],
                "nombre": r.get("stop_name", "").strip() or None,
                "modo": infer_mode(r["stop_id"]),
                "linea": r.get("zone_id") or None,
                # PostGIS WKT EWKT: SRID=4326;POINT(lng lat)
                "geom": f"SRID=4326;POINT({lng} {lat})",
            })
    return rows


def main() -> int:
    load_dotenv(Path(__file__).parent.parent / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar en .env", file=sys.stderr)
        return 1
    if not STOPS_FILE.exists():
        print(f"ERROR: no existe {STOPS_FILE}", file=sys.stderr)
        return 1

    client = create_client(url, key)
    rows = read_stops()
    print(f"Leídas {len(rows)} paradas de {STOPS_FILE.name}")

    # Borra e inserta (idempotente). Usa upsert para permitir re-ingestas.
    inserted = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        client.table("estaciones_transporte").upsert(batch).execute()
        inserted += len(batch)
        print(f"  batch {i // BATCH_SIZE + 1}: {inserted}/{len(rows)}")

    print(f"OK: {inserted} estaciones cargadas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
