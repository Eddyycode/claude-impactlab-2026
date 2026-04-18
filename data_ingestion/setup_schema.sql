-- ============================================================
-- donde-vivir-cdmx · schema mínimo para Supabase
-- Único propósito: guardar estaciones GTFS + consulta por radio
-- ============================================================
-- Ejecutar una sola vez en el SQL Editor del dashboard Supabase
-- (o aplicar vía `mcp__claude_ai_Supabase__apply_migration`).
-- Todo lo demás (crimen, aire, sismos, inundaciones, agua) se
-- consulta en vivo a CKAN vía cdmx-mcp — no requiere tablas.

-- 1. Extensión PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Tabla de estaciones de transporte (Metro / Metrobús / RTP / Trolebús / Cablebús)
CREATE TABLE IF NOT EXISTS estaciones_transporte (
  stop_id  TEXT PRIMARY KEY,
  nombre   TEXT,
  modo     TEXT,   -- 'metro' | 'metrobus' | 'rtp' | 'trolebus' | 'cablebus'
  linea    TEXT,
  geom     geometry(Point, 4326)
);

CREATE INDEX IF NOT EXISTS estaciones_transporte_geom_idx
  ON estaciones_transporte USING GIST (geom);

-- 3. Función: estaciones dentro de un radio (metros) desde un punto lat/lng
--    Devuelve hasta 10 estaciones ordenadas por distancia.
--    Nota PostGIS: ST_MakePoint(lng, lat) — longitud PRIMERO.
CREATE OR REPLACE FUNCTION stations_within_radius(
  lat FLOAT, lng FLOAT, radius_m INT DEFAULT 800
)
RETURNS TABLE(
  stop_id     TEXT,
  nombre      TEXT,
  modo        TEXT,
  linea       TEXT,
  distancia_m FLOAT
)
LANGUAGE sql STABLE AS $$
  SELECT
    stop_id,
    nombre,
    modo,
    linea,
    ST_Distance(
      geom::geography,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
    ) AS distancia_m
  FROM estaciones_transporte
  WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
    radius_m
  )
  ORDER BY distancia_m
  LIMIT 10;
$$;

-- 4. Row Level Security: la tabla es de solo-lectura pública (no hay datos sensibles).
ALTER TABLE estaciones_transporte ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "estaciones_transporte_read_anon" ON estaciones_transporte;
CREATE POLICY "estaciones_transporte_read_anon"
  ON estaciones_transporte
  FOR SELECT
  TO anon, authenticated
  USING (true);
