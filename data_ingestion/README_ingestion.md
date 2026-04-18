# Ingesta de datos — donde-vivir-cdmx

Una sola ingesta: las estaciones GTFS a Supabase.
Todo lo demás (crimen, aire, sismos, inundaciones, agua) se consulta en vivo
vía `cdmx-mcp` contra CKAN CDMX.

## GTFS · estaciones de transporte

### 1. Descargar el feed

- URL: <https://datos.cdmx.gob.mx/dataset/gtfs>
- Descargar el ZIP más reciente.
- Extraer **solo** `stops.txt` a `data_ingestion/raw/stops.txt`.

### 2. Aplicar schema (si no se ha hecho)

Ya aplicado el 2026-04-18 via `mcp__claude_ai_Supabase__apply_migration` al
proyecto `claude-impact` (ref `pcbhmmsifoycmcybwkvy`).

Si se vuelve a aplicar, correr `setup_schema.sql` en el SQL Editor.

### 3. Cargar las estaciones

```bash
# Desde la raíz del repo, con .env configurado
cd data_ingestion
python load_gtfs_stops.py
```

Requisitos:
- Python 3.10+
- `pip install supabase python-dotenv` (se agregarán a `gateway/requirements.txt`
  o se puede instalar en un venv separado para ingesta)
- `.env` con `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` configurados

### 4. Verificación

```sql
-- En el SQL Editor de Supabase:
SELECT count(*) FROM estaciones_transporte;           -- debe ser ~11,300+
SELECT * FROM stations_within_radius(19.4326, -99.1332, 500);
```

---

## Limitación conocida del feed actual

El GTFS de `datos.cdmx.gob.mx` que se descargó (2026-04-18) **solo contiene
paradas de RTP / autobuses** — todos los `stop_id` llevan el prefijo `B_`.
**No incluye Metro ni Metrobús.**

Impacto en el scoring:
- La dimensión "transporte" se calcula con menos densidad que la realidad.
- Se documenta en `PROPUESTA.md` como scope del MVP.

Si hay tiempo post-MVP: buscar feeds separados:
- Metro CDMX: suele exponerse como GeoJSON/shapefile en el portal.
- Metrobús: tiene su propio GTFS (no siempre en el portal CDMX).

La tabla `estaciones_transporte` ya soporta `modo='metro' | 'metrobus' | …` —
solo hay que cargar otros feeds con el mismo schema.
