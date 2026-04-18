# DATASET_SLUGS.md

Slugs CKAN descubiertos en `datos.cdmx.gob.mx` para uso con `cdmx-mcp`.
Cada entrada trae el `dataset_id` (slug de la URL), el `resource_id` del
CSV datastore-activo (requerido por `datastore_search` / `datastore_search_sql`),
el tamaño y los campos relevantes para nuestras queries.

> **Verificado el 2026-04-18** — si algo deja de funcionar, rehacer con
> `curl "https://datos.cdmx.gob.mx/api/3/action/package_search?q=<tema>"`.

> **Nota CKAN 2.10:** en `datastore_search_sql` los identificadores van
> entre `"..."` y los literales entre `'...'`. Los `resource_id` son UUIDs.

---

## 1. Riesgo sísmico

- **dataset_id:** `atlas-de-riesgo-sismico`
- **resource_id:** `4f23c6c5-1b2b-410e-8589-a720d7b3db58`
- **total_rows:** 4908
- **título:** Atlas de Riesgo — Sísmico (SPCGIR)

Campos útiles:

| campo | tipo | uso |
|---|---|---|
| `alcaldia` | text | **filtro principal** (ej. `'CUAUHTEMOC'`) |
| `fenomeno` | text | tipo de fenómeno (sísmico en este dataset) |
| `intensidad` | text | categoría de intensidad |
| `r_p_v_e` | text | riesgo + peligro + vulnerabilidad + exposición |
| `descripcio` | text | descripción libre |
| `geo_point_2d` | text | `"lat, lng"` |
| `geo_shape` | text | GeoJSON del polígono |

Ejemplo de query via `query_records`:
```
query_records(
  dataset_id="atlas-de-riesgo-sismico",
  where="\"alcaldia\" = 'CUAUHTEMOC'",
  select="alcaldia, intensidad, r_p_v_e",
  limit=20
)
```

---

## 2. Riesgo de inundaciones

- **dataset_id:** `atlas-de-riesgo-inundaciones`
- **resource_id:** `b6249921-7811-4a48-a82a-60fcec5e5184`
- **total_rows:** 4908
- **título:** Atlas de Riesgo — Inundaciones (SPCGIR)

Campos útiles:

| campo | tipo | uso |
|---|---|---|
| `alcaldia` | text | **filtro principal** |
| `fenomeno` | text | tipo (inundación) |
| `intensidad` | text | nivel cualitativo |
| `intens_num` | text | nivel numérico |
| `intens_uni` | text | unidad (cm/m) |
| `period_ret` | text | periodo de retorno (años) |
| `r_p_v_e` | text | riesgo compuesto |
| `geo_point_2d` | text | `"lat, lng"` |

---

## 3. Reportes de agua (SACMEX)

- **dataset_id:** `reportes-de-agua`
- **título:** Reportes de agua

Este dataset tiene **2 recursos datastore-activos** (split por rango de fechas):

| resource_id | cobertura | total_rows |
|---|---|---|
| `a8069e94-c7cb-45d7-8166-561e80884422` | **2022–2024** (usar este para MVP) | 313,756 |
| `65a6b1a6-5d6e-49b9-aeed-ca7b22e8de03` | histórico 2018–2021 | — |

Campos útiles (2022–2024):

| campo | tipo | uso |
|---|---|---|
| `colonia_catalogo` | text | **filtro principal por colonia** |
| `alcaldia_catalogo` | text | filtro por alcaldía |
| `fecha_reporte` | timestamp | para filtrar últimos 6 meses |
| `clasificacion` | text | tipo de reporte |
| `reporte` | text | descripción |
| `longitud`, `latitud` | numeric | ubicación |

Query típica (últimos 6 meses por colonia):
```
query_records(
  dataset_id="reportes-de-agua",
  where="\"colonia_catalogo\" = 'NARVARTE PONIENTE' AND \"fecha_reporte\" >= '2025-10-18'"
)
```

---

## 4. Zona cero sismo 2017

- **dataset_id:** `atlas-de-riesgo-zona-cero-2017`
- **resource_id:** `1576dca2-cf11-41d4-b079-da0533635a04`
- **total_rows:** 22
- **título:** Atlas de Riesgo — Zona Cero 2017

Campos:

| campo | tipo | uso |
|---|---|---|
| `zona` | text | nombre de zona |
| `geo_point_2d`, `geo_shape` | text | geometría |

> **Solo 22 filas** — son los polígonos de zonas afectadas. Para saber si una
> dirección está en zona cero, hay que hacer point-in-polygon contra `geo_shape`.
> Para el MVP basta con restar puntos al score sísmico si el `geo_point_2d`
> está cerca.

---

## 5. Alternativa descartada — zonificación sísmica por colonia

- **dataset_id:** `zonificacion-sismica-por-colonia`
- **¿Por qué NO lo usamos?** Ningún recurso tiene `datastore_active=true`,
  solo SHP y GeoJSON como download. No es queryable vía `query_records`.
  Si se necesita a futuro, se carga a Supabase con GeoPandas.

---

## Shortcuts de `cdmx-mcp` (sin necesidad de slug)

Estos se usan con tools directas, sin `query_records`:

| Tool | Cubre |
|---|---|
| `crime_hotspots(year, alcaldia, top_n)` | FGJ (delitos) |
| `air_quality_now(zone?, limit)` | SIMAT (calidad del aire) |
| `ecobici_status(near_lat, near_lng, radius_m)` | ECOBICI en vivo |
| `denue_near(lat, lng, radius_m, keyword)` | DENUE INEGI (requiere `INEGI_TOKEN`) |
| `list_datasets(search)` | catálogo completo CKAN |
| `describe_dataset(dataset_id)` | schema de un dataset |

---

## Mapeo a dimensiones del scoring 1–10

| Dimensión | Tool / slug | Filtro clave |
|---|---|---|
| Seguridad | `crime_hotspots` | `alcaldia` |
| Aire | `air_quality_now` | (automático) |
| Sísmico | `query_records("atlas-de-riesgo-sismico")` | `alcaldia` |
| Inundación | `query_records("atlas-de-riesgo-inundaciones")` | `alcaldia` |
| Agua | `query_records("reportes-de-agua", resource=2022-2024)` | `colonia_catalogo` + `fecha_reporte` |
| Integridad 2017 | `query_records("atlas-de-riesgo-zona-cero-2017")` + cálculo geo local | — |
| Transporte | Supabase `stations_within_radius(lat, lng, 800)` | lat/lng |
| ECOBICI | `ecobici_status(near_lat, near_lng, 500)` | lat/lng |
| Servicios | `denue_near(lat, lng, 800, keyword)` | lat/lng |
