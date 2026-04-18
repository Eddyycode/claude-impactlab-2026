# PROPUESTA — ¿Dónde vivir en CDMX? con `cdmx-mcp` (mcp cesar)

Esta propuesta reescribe la arquitectura del proyecto para **reutilizar el MCP
server `cdmx-mcp`** que ya está incluido como submódulo en `mcp cesar/` en vez
de construir un MCP propio. El objetivo: llegar al demo del hackathon con menos
código, menos ingesta y el mismo alcance funcional.

> Submódulo: `mcp cesar/` → <https://github.com/devcsar/cdmx-mcp>
> Stack del MCP: Python 3.10+ · FastMCP · CKAN 2.10 (datos.cdmx.gob.mx) · GBFS (ECOBICI) · DENUE (INEGI)

---

## TL;DR de la propuesta

1. **Borrar** el plan de construir `mcp_server/` propio.
2. **Correr `cdmx-mcp` tal cual** desde `mcp cesar/` como proceso separado (stdio).
3. El **gateway FastAPI** sigue existiendo, pero ahora:
   - Se conecta al MCP server vía el SDK oficial de MCP (cliente stdio).
   - Expone las 9 tools de `cdmx-mcp` a Claude API con tool use.
   - Agrega **2 tools propias** que el MCP no cubre: `geocode_address` (Nominatim)
     y `get_transit_access` (Supabase PostGIS con GTFS).
4. La **única ingesta** sigue siendo el GTFS → Supabase (una tabla).
5. Los datasets de sismos, inundaciones, agua y edificios dañados 2017 que **no
   vienen precargados** en `cdmx-mcp` se consultan con su tool genérica
   `query_records(dataset_id, where=...)` — no hay que tocar el MCP.

---

## Qué cubre `cdmx-mcp` out-of-the-box

| Dimensión del proyecto | Tool del MCP a usar |
|---|---|
| Seguridad / crimen | `crime_hotspots(year, alcaldia, category, top_n)` |
| Calidad del aire | `air_quality_now(zone?, limit)` |
| Negocios cercanos (opcional, contexto) | `denue_near(lat, lng, radius_m, keyword)` |
| Movilidad en vivo (ECOBICI) | `ecobici_status(near_lat, near_lng, radius_m)` |
| **Cualquier dataset CKAN** (sismos, inundaciones, agua, 2017) | `query_records(dataset_id, where, select, order_by, limit)` |
| Catálogo / descubrimiento | `list_datasets`, `describe_dataset` |
| Agregaciones server-side | `aggregate(dataset_id, group_by, metric, where)` |

Shortcuts de dataset que ya soporta: `fgj`, `911`, `ids`, `aire`.

Para sismos/inundaciones/agua/2017 hay que pasar el **slug completo** del dataset
en `datos.cdmx.gob.mx` (pendiente verificar durante setup — ver §Riesgos).

---

## Qué NO cubre `cdmx-mcp` (lo agregamos nosotros)

| Necesidad | Solución |
|---|---|
| Geocodificar una dirección en texto a lat/lng | Tool `geocode_address` en el gateway usando Nominatim |
| Identificar AGEB / colonia / alcaldía a partir de lat/lng | Reverse geocode de Nominatim + tabla de colonias (CKAN) |
| Estaciones de transporte en un radio (Metro/Metrobús/RTP) | Tool `get_transit_access` en el gateway, contra Supabase PostGIS con GTFS `stops.txt` |
| Artefacto HTML final del reporte | Tool `generate_report` en el gateway (plantilla Jinja2 local, sin datos externos) |

Estas 3 tools **no se agregan al MCP**, se definen en el gateway para no tocar
el submódulo de terceros. Mantener `cdmx-mcp` sin fork lo hace trivialmente
actualizable con `git submodule update --remote`.

---

## Nueva arquitectura

```
Vue (fetch) ──► POST /chat ──► Gateway (FastAPI)
                                    │
                                    ├──► Claude API (tool use loop)
                                    │
                                    ├──► cdmx-mcp  (stdio, FastMCP)
                                    │         └─► CKAN · GBFS · DENUE
                                    │
                                    ├──► Nominatim  (geocode_address)
                                    │
                                    └──► Supabase PostGIS  (get_transit_access)
```

**Cambios respecto al CLAUDE.md actual:**
- Ya no hay `mcp_server/` en el repo.
- El gateway habla con `cdmx-mcp` vía **MCP client stdio**, no por HTTP.
- El gateway **agrega** 3 tools locales al set que expone a Claude.
- Sigue habiendo Supabase (una tabla) y Nominatim.

---

## Estructura del repo (propuesta)

```
claude-impactlab-2026/
├── CLAUDE.md
├── PROPUESTA.md              ← este archivo
├── .env · .env.example
├── .gitmodules
│
├── mcp cesar/                ← SUBMÓDULO ya clonado, no editar
│   └── (cdmx-mcp tal cual)
│
├── frontend/                 ← Vue 3 + Vite (sin cambios vs CLAUDE.md)
│
├── gateway/                  ← FastAPI
│   ├── main.py               ← POST /chat + tool-use loop
│   ├── mcp_client.py         ← cliente stdio que levanta `uv run cdmx-mcp`
│   ├── tools/
│   │   ├── geocode.py        ← Nominatim
│   │   ├── transit.py        ← Supabase PostGIS
│   │   └── report.py         ← genera el HTML del reporte
│   ├── tool_registry.py      ← une tools del MCP + tools locales en un solo array
│   ├── requirements.txt
│   └── pyproject.toml
│
└── data_ingestion/
    ├── setup_schema.sql
    ├── load_gtfs_stops.py
    └── README_ingestion.md
```

---

## Cómo habla el gateway con `cdmx-mcp`

El gateway levanta el MCP como **subproceso stdio** al iniciar, y mantiene la
sesión abierta mientras vive. Usamos el SDK oficial `mcp` de Python.

```python
# gateway/mcp_client.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(
    command="uv",
    args=["--directory", "../mcp cesar", "run", "cdmx-mcp"],
)

class CdmxMcp:
    async def __aenter__(self):
        self._ctx = stdio_client(params)
        self.read, self.write = await self._ctx.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        await self.session.initialize()
        return self

    async def list_tools(self):
        return (await self.session.list_tools()).tools

    async def call(self, name: str, arguments: dict):
        return await self.session.call_tool(name, arguments)

    async def __aexit__(self, *a):
        await self.session.__aexit__(*a)
        await self._ctx.__aexit__(*a)
```

En `main.py` se instancia una vez en `lifespan` de FastAPI y se reutiliza en
cada request. Así no pagamos el costo de levantar el MCP por request.

---

## Registro unificado de tools para Claude API

```python
# gateway/tool_registry.py
LOCAL_TOOLS = [
    {
        "name": "geocode_address",
        "description": "Convierte una dirección o colonia de CDMX en lat/lng + alcaldía + colonia.",
        "input_schema": {
            "type": "object",
            "properties": {"direccion": {"type": "string"}},
            "required": ["direccion"],
        },
    },
    {
        "name": "get_transit_access",
        "description": "Estaciones de Metro/Metrobús/RTP en un radio desde un punto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number"},
                "lng": {"type": "number"},
                "radio_m": {"type": "integer", "default": 800},
            },
            "required": ["lat", "lng"],
        },
    },
    {
        "name": "generate_report",
        "description": "Genera el artefacto HTML final con scores y mapa.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direccion": {"type": "string"},
                "scores": {"type": "object"},
                "resumen": {"type": "string"},
            },
            "required": ["direccion", "scores", "resumen"],
        },
    },
]

async def build_tool_list(mcp_client):
    """Une las 9 tools de cdmx-mcp + las 3 locales en el formato de Claude API."""
    mcp_tools = await mcp_client.list_tools()
    remote = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]
    return remote + LOCAL_TOOLS
```

## Despacho de tool calls en el loop

```python
# gateway/main.py (extracto)
LOCAL_DISPATCH = {
    "geocode_address": tools.geocode.geocode_address,
    "get_transit_access": tools.transit.get_transit_access,
    "generate_report": tools.report.generate_report,
}

async def call_tool(name: str, args: dict, mcp_client):
    if name in LOCAL_DISPATCH:
        return await LOCAL_DISPATCH[name](**args)
    # cualquier otro nombre → MCP cesar
    result = await mcp_client.call(name, args)
    return result.content  # lista de content blocks MCP, serializable a string
```

---

## Mapeo del flujo conversacional a tools

Cuando el usuario pregunta por una dirección, Claude ahora ejecuta:

1. `geocode_address(direccion)` *(local)* → `{lat, lng, colonia, alcaldia}`
2. En paralelo:
   - `crime_hotspots(year=2025, alcaldia=...)` *(cdmx-mcp)*
   - `air_quality_now(zone=...)` *(cdmx-mcp)*
   - `query_records(dataset_id="atlas-riesgo-sismico", where='alcaldia=\'...\'')` *(cdmx-mcp)*
   - `query_records(dataset_id="atlas-riesgo-inundaciones", where='alcaldia=\'...\'')` *(cdmx-mcp)*
   - `query_records(dataset_id="reportes-de-agua", where='colonia=\'...\'')` *(cdmx-mcp)*
   - `get_transit_access(lat, lng, radio_m=800)` *(local)*
3. Síntesis en español claro.
4. `generate_report(direccion, scores, resumen)` *(local)* → HTML.

Ya no tiene sentido mantener `get_seismic_risk`, `get_flood_risk`,
`get_crime_stats`, `get_water_reliability`, `get_air_quality`,
`get_damaged_buildings_nearby` como tools separadas: el system prompt le indica
a Claude qué dataset/slug usar con `query_records` y `crime_hotspots` /
`air_quality_now` lo resuelven directamente.

**Trade-off:** menos tools custom = menos código, pero el system prompt se
vuelve más largo para guiar a Claude sobre qué slugs usar para riesgo sísmico
/ inundaciones / agua.

---

## System prompt (borrador actualizado)

```
Eres un agente experto en calidad de vida urbana en CDMX. Ayudas a personas a
evaluar colonias y direcciones.

Tools disponibles:
- geocode_address(direccion): SIEMPRE úsala primero.
- crime_hotspots(year, alcaldia, top_n=10): seguridad por alcaldía.
- air_quality_now(zone): calidad del aire reciente.
- query_records(dataset_id, where, ...): para sismos, inundaciones, agua,
  edificios dañados 2017. Usa estos slugs:
    • "atlas-riesgo-sismico"       → riesgo sísmico por alcaldía
    • "atlas-riesgo-inundaciones"  → inundaciones por alcaldía
    • "reportes-de-agua"           → fallas de suministro por colonia
    • "inmuebles-danados-2017"     → edificios afectados por el sismo
- get_transit_access(lat, lng, radio_m=800): Metro/Metrobús en radio.
- generate_report(direccion, scores, resumen): SIEMPRE termina con esto.

Reglas:
1. Empieza con geocode_address.
2. Ejecuta las tools de evaluación en paralelo.
3. Si una tool falla, continúa con las demás e indícalo en el resumen.
4. MVP cubre Cuauhtémoc, Benito Juárez, Coyoacán. Fuera de eso, responde
   honestamente y ofrece la alcaldía más cercana.
5. Termina con generate_report.
```

---

## Sistema de calificación 1–10 (consulta por colonia/dirección)

Cada vez que un usuario final consulta una nueva dirección o colonia, el agente
devuelve un set de **9 métricas normalizadas en escala 1–10** (10 = mejor para
vivir, 1 = peor), una por dimensión urbana, **más un score global ponderado**.
Toda métrica se deriva de **datos abiertos de gobierno** (CKAN CDMX, SIMAT,
GTFS, GBFS ECOBICI, DENUE INEGI) — nunca de estimaciones, scraping o inferencia.

> **⚠ Cambio de convención.** El `CLAUDE.md` original usaba una escala 1–3
> donde **1 era mejor** (bajo riesgo). Esta propuesta la reemplaza por 1–10
> donde **10 es mejor** (mejor para vivir). Al actualizar `ScoreCard.vue` hay
> que invertir la lógica de color y etiquetas — el snippet actualizado está
> más abajo.

### Las 9 dimensiones evaluadas

| # | Dimensión | Tool / fuente de gobierno | Insumo numérico | Fórmula → 1–10 |
|---|---|---|---|---|
| 1 | **Seguridad** | `crime_hotspots` · FGJ CDMX | delitos por 1000 hab en últimos 12 meses (colonia) | 10 si ≤ p10 CDMX · 1 si ≥ p90 · lineal entre percentiles |
| 2 | **Calidad del aire** | `air_quality_now` · SIMAT | PM2.5 promedio 7 días (µg/m³) en estación más cercana | 10 si ≤ 12 · 5 si 25 · 1 si ≥ 55 (referencia OMS) |
| 3 | **Riesgo sísmico** | `query_records("atlas-riesgo-sismico")` · Atlas de Riesgo CDMX | zona sísmica (I / II / III) | 10 zona I · 6 zona II · 2 zona III — resta 2 si cae en polígono 2017 |
| 4 | **Riesgo de inundación** | `query_records("atlas-riesgo-inundaciones")` · Atlas de Riesgo CDMX | nivel (bajo / medio / alto / muy alto) | 10 / 7 / 4 / 1 respectivamente |
| 5 | **Confiabilidad del agua** | `query_records("reportes-de-agua")` · SACMEX | # reportes por 1000 hab en 6 meses (colonia) | 10 si ≤ p10 · 1 si ≥ p90 · lineal |
| 6 | **Acceso a transporte** | `get_transit_access` (local) · GTFS CDMX | # estaciones en 800 m ponderadas por modo | Metro ×3 · Metrobús ×2 · RTP/Trolebús/Cablebús ×1 · tope 10 |
| 7 | **Integridad estructural 2017** | `query_records("inmuebles-danados-2017")` · Plataforma CDMX | # inmuebles afectados en radio 300 m | parte de 10 y resta 1 por inmueble (piso 1) · solo puede bajar el score |
| 8 | **Servicios cercanos** | `denue_near` · DENUE (INEGI) | cobertura de 4 categorías (súper, farmacia, escuela, hospital) en 800 m | 2.5 pts por categoría cubierta · tope 10 |
| 9 | **Movilidad ECOBICI** | `ecobici_status` · GBFS ECOBICI | # cicloestaciones en 500 m | 0→1 · 1→4 · 2→6 · 3→8 · ≥4→10 |

> **Core vs. enrichment.** Dimensiones 1–7 son **obligatorias** — si alguna falla
> se reporta como faltante pero sigue intentándose. Dimensiones 8 y 9 son
> enriquecimiento: si DENUE no tiene token o ECOBICI falla, se omiten sin drama.

### Score global ponderado

```
score_global = Σ (peso_i × score_i) / Σ pesos_activos
```

**Pesos default** (suman 100, calibrados para CDMX post-2017):

| Dimensión | Peso default |
|---|---|
| Seguridad | 20 |
| Riesgo sísmico | 18 |
| Confiabilidad del agua | 14 |
| Acceso a transporte | 14 |
| Calidad del aire | 12 |
| Riesgo de inundación | 8 |
| Integridad estructural 2017 | 8 |
| Servicios cercanos | 4 |
| ECOBICI | 2 |

### Personalización por usuario

El payload de `POST /chat` ya admite `preferences`. Se extiende para aceptar
pesos del usuario:

```json
{
  "messages": [...],
  "preferences": {
    "idioma": "es",
    "prioridad_weights": {
      "seguridad": 30,
      "agua": 25,
      "transporte": 20
    }
  }
}
```

Reglas de aplicación:
- Los pesos del usuario **reemplazan** los default de las dimensiones que menciona.
- Las dimensiones no mencionadas conservan su peso default.
- Al final se **renormaliza** para que la suma de pesos activos sea 100.
- Si una dimensión no se pudo calcular, su peso se redistribuye entre las demás.

### Etiqueta y color por score

| Score | Etiqueta | Color | Semántica |
|---|---|---|---|
| 8.5–10.0 | Excelente | verde oscuro `#15803d` | Recomendado sin reservas |
| 7.0–8.4 | Bueno | verde `#22c55e` | Buena opción para vivir |
| 5.5–6.9 | Aceptable | amarillo `#f59e0b` | Revisa los tradeoffs |
| 4.0–5.4 | Preocupante | naranja `#f97316` | Solo con razón de peso |
| 1.0–3.9 | Evitar | rojo `#ef4444` | No recomendado |

### Shape de respuesta de `generate_report`

```python
def generate_report(direccion, scores, resumen):
    """
    scores: {
      "global": 7.3,
      "etiqueta_global": "Bueno",
      "dimensiones": [
        {
          "id": "seguridad",
          "nombre": "Seguridad",
          "score": 6.2,
          "peso_aplicado": 20,
          "fuente": "FGJ CDMX — carpetas de investigación",
          "dataset_id": "fgj",
          "consultado_en": "2026-04-18",
          "dato_bruto": "48 delitos / 1000 hab últimos 12m",
          "detalle": "Tendencia estable vs. trimestre previo"
        },
        ...
      ],
      "faltantes": [
        {"id": "ecobici", "razon": "GBFS feed sin estaciones en 500 m"}
      ]
    }
    """
```

### Reglas de transparencia (requisito del demo)

1. **Cada métrica cita la fuente.** Nombre del dataset + fecha de consulta, al
   lado del score. Sin eso, el score no se muestra.
2. **Dato bruto antes que score.** El usuario ve "48 delitos/1000 hab" primero
   y el "6.2/10" como síntesis. Nunca solo el score.
3. **Dimensiones faltantes se listan** explícitamente en el reporte con el
   motivo ("no hay estación SIMAT con datos recientes en 3 km").
4. **Solo fuentes gubernamentales o estándares abiertos** — CKAN CDMX, SIMAT,
   GTFS, GBFS ECOBICI, DENUE INEGI. Nada scrapeado ni inferido.
5. **Claude nunca inventa números.** Si una tool devuelve vacío, la dimensión
   entra a `faltantes`, no se estima.

### ScoreCard.vue — actualizado a 1–10

```vue
<script setup>
defineProps({
  dimension: String,
  score:     Number,    // 1.0–10.0
  peso:      Number,    // 0–100 (peso aplicado tras renormalización)
  fuente:    String,
  consultadoEn: String, // YYYY-MM-DD
  datoBruto: String,
  detalle:   String,
})

const colorByScore = (s) =>
  s >= 8.5 ? '#15803d' :
  s >= 7.0 ? '#22c55e' :
  s >= 5.5 ? '#f59e0b' :
  s >= 4.0 ? '#f97316' : '#ef4444'

const etiqueta = (s) =>
  s >= 8.5 ? 'Excelente' :
  s >= 7.0 ? 'Bueno' :
  s >= 5.5 ? 'Aceptable' :
  s >= 4.0 ? 'Preocupante' : 'Evitar'
</script>

<template>
  <div class="score-card">
    <header class="sc-header">
      <p class="dimension">{{ dimension }}</p>
      <span class="peso">Peso: {{ peso }}%</span>
    </header>

    <div class="score-row">
      <span class="score" :style="{ color: colorByScore(score) }">
        {{ score.toFixed(1) }}<small>/10</small>
      </span>
      <span class="badge" :style="{ background: colorByScore(score) }">
        {{ etiqueta(score) }}
      </span>
    </div>

    <p class="dato-bruto">{{ datoBruto }}</p>
    <p class="detalle">{{ detalle }}</p>
    <p class="fuente">
      Fuente: {{ fuente }} · consulta {{ consultadoEn }}
    </p>
  </div>
</template>
```

### Agregado al system prompt

```
Al terminar la evaluación de una dirección o colonia:

- Cada dimensión debe tener un score numérico decimal entre 1.0 y 10.0
  (10 = mejor para vivir, 1 = peor).
- Cada dimensión debe declarar la fuente de gobierno (nombre del dataset
  + fecha de consulta) en el campo `fuente`.
- Calcula el score global como promedio ponderado usando los pesos default
  o los enviados por el usuario en preferences.prioridad_weights.
- Si una dimensión no se pudo calcular (tool vacía, dataset no cubre el
  área, error), agrégala a `faltantes` con el motivo y renormaliza los
  pesos restantes.
- NUNCA inventes un número sin dato de gobierno detrás. Prefiere dejar
  la dimensión en `faltantes` a estimar.
```

### Ejemplo de salida para el demo

Consulta: *"¿Es buena zona para vivir la colonia Narvarte Poniente?"*

```
Score global: 7.6/10 — Bueno

★ 7.8  Seguridad             (peso 20%) · FGJ CDMX · 2026-04-18
★ 6.4  Calidad del aire      (peso 12%) · SIMAT · 2026-04-18
★ 6.0  Riesgo sísmico        (peso 18%) · Atlas Riesgo CDMX · 2026-04-18
★ 9.0  Riesgo de inundación  (peso  8%) · Atlas Riesgo CDMX · 2026-04-18
★ 7.2  Agua                  (peso 14%) · SACMEX · 2026-04-18
★ 9.5  Transporte            (peso 14%) · GTFS CDMX · 2026-04-18
★ 8.0  Integridad 2017       (peso  8%) · Plataforma CDMX · 2026-04-18
★ 7.5  Servicios cercanos    (peso  4%) · DENUE · 2026-04-18
★ 6.0  ECOBICI               (peso  2%) · GBFS · 2026-04-18
```

---

## Checklist de setup del MCP (antes del evento)

```bash
# 1. Inicializar submódulo (si aún no)
git submodule update --init --recursive

# 2. Instalar uv (el MCP lo requiere — ver mcp cesar/README.md)
#    Windows PowerShell:
#    irm https://astral.sh/uv/install.ps1 | iex

# 3. Instalar deps del MCP
cd "mcp cesar"
uv sync
uv run python tests/smoke_test.py      # debe decir "smoke: OK"

# 4. (Opcional) Test live contra el portal
CDMX_MCP_LIVE=1 uv run python tests/live_test.py

# 5. (Opcional) Token INEGI si se usa denue_near
#    export INEGI_TOKEN=...
```

El gateway no necesita que el MCP esté corriendo como servicio HTTP — lo
arranca como subproceso stdio automáticamente en `lifespan`.

---

## Riesgos y cosas que hay que verificar durante el setup

1. **Slugs de datasets no precargados.** `cdmx-mcp` tiene shortcuts para `fgj`,
   `911`, `ids`, `aire`. Para sismos / inundaciones / agua / 2017 hay que
   **descubrir el `dataset_id` real** en el portal con `list_datasets(search="sismico")`
   al inicio del hackathon. Apuntarlos en un archivo `DATASET_SLUGS.md` para no
   perder tiempo después. **→ Tarea de la hora 0 de Dev A.**

2. **Columnas y tipos.** Cada dataset tiene columnas distintas. Usar
   `describe_dataset(dataset_id)` antes de armar `where=...`. En CKAN 2.10 los
   identificadores van entre `"..."` y los literales entre `'...'`.

3. **`cdmx-mcp` como subproceso stdio dentro de FastAPI.** Requiere que `uv`
   esté en el PATH del proceso del gateway. En Windows puede necesitar ruta
   absoluta. Si no funciona en 30 min, plan B: correr `cdmx-mcp` como proceso
   aparte y hablar con él por HTTP (agregar un wrapper FastAPI mínimo dentro
   del submódulo **sin commitear**).

4. **Geocodificación de colonias.** Nominatim puede fallar con nombres ambiguos
   ("Narvarte" tiene Poniente y Oriente). Fallback: catálogo CKAN de colonias.

5. **Rate limit de Nominatim.** 1 req/s. El gateway debe cachear en memoria por
   dirección normalizada (suficiente para el demo).

---

## Beneficios de este approach

- **Menos código propio** — ahorramos las 5 tools de CKAN + toda la ingesta.
- **Más fresco** — al consultar CKAN en vivo, los datos son del día, no de un
  snapshot de hace semanas.
- **Reusable** — el MCP ya es pitchable por sí solo ("usamos `cdmx-mcp`, un
  MCP open-source de datos CDMX") y le suma narrativa al demo.
- **Actualizable** — `git submodule update --remote` trae features nuevas sin
  tocar nuestro código.

## Qué se pierde

- Control fino sobre cómo se hace cada query (hay que confiar en `cdmx-mcp`
  y su formato de respuesta).
- Un poco más de complejidad operativa (dos procesos: gateway + MCP stdio).

---

## Siguiente paso sugerido

Revisar esta propuesta, decidir si nos vamos por este camino, y si sí:

1. Actualizar `CLAUDE.md` borrando la sección "Tools del servidor MCP" y
   reemplazándola por el §"Mapeo del flujo conversacional a tools" de este doc.
2. Borrar la sección de scripts de ingesta `02_*` a `07_*` del CLAUDE.md.
3. Agregar `mcp cesar/` al §"Comandos de desarrollo" con el `uv sync` + smoke test.
4. Crear `DATASET_SLUGS.md` vacío (se llena durante el evento).

---

## Plan de desarrollo — 2 devs, cero merge conflicts

Somos 2 devs. **Dev A** (tú) = backend, MCP, gateway, datos, scoring.
**Dev B** (tu compañero) = frontend Vue, UX, mapa, demo.

Estrategia: dividir por **directorios de forma estricta**. Cada dev toca solo
lo suyo y se comunican a través de un **contrato de API congelado** al inicio.
Con esta disciplina, `git merge` nunca genera conflictos — porque nunca editan
los mismos archivos.

### Matriz de propiedad (la regla de oro)

| Archivo / directorio | Dueño | ¿El otro dev puede tocarlo? |
|---|---|---|
| `frontend/**` | **Dev B** | Nunca. Ni un CSS. |
| `gateway/**` | **Dev A** | Nunca. |
| `data_ingestion/**` | **Dev A** | Nunca. |
| `mcp cesar/` (submódulo) | **Dev A** — solo setup | Nadie edita su contenido |
| `.env.backend.example` | **Dev A** | No |
| `.env.frontend.example` | **Dev B** | No |
| `.gitignore` | **Dev A** | Dev B avisa por chat antes de tocarlo |
| `.gitmodules` | **Dev A** | No |
| `DATASET_SLUGS.md` | **Dev A** | No |
| `API_CONTRACT.md` | **Dev A**, pair-editado con Dev B en el kickoff | Solo en checkpoints |
| `CLAUDE.md` · `PROPUESTA.md` | Rotativo, solo en checkpoints | Nunca durante la misma hora |
| `README.md` | Se crea al final, Dev A | — |
| `.env` (local, no se commitea) | Cada dev el suyo | — |

**Regla:** si una tarea requiere editar un archivo del otro dueño, la hace ese dev.
Sin atajos. Sin "solo cambio una línea".

> **Truco para `.env.example`:** en vez de un solo archivo compartido, se crean
> **dos** (`.env.backend.example` y `.env.frontend.example`). Cada dev el suyo,
> cero conflicto. Al final se concatenan en un único `.env.example` en el freeze.

### Archivo de contrato — la única dependencia entre los dos

Crear `gateway/API_CONTRACT.md` (owned by Dev A) **en el kickoff (minuto 30)**.
Pair-editado 15 min con Dev B presente. Define:

1. **Request shape** de `POST /chat`:
   ```json
   {
     "messages": [{"role": "user", "content": "..."}, ...],
     "preferences": {
       "idioma": "es",
       "prioridad_weights": { "seguridad": 30, "agua": 25 }
     }
   }
   ```
2. **Response shape** — ver §"Shape de respuesta de `generate_report`".
3. **IDs canónicos de dimensión**: `seguridad`, `aire`, `sismico`, `inundacion`,
   `agua`, `transporte`, `integridad_2017`, `servicios`, `ecobici`.
4. **Fixture JSON completo de Narvarte Poniente** — Dev B lo usa como mock
   mientras Dev A construye el gateway.

Una vez congelado: **no se cambia sin aviso explícito.** Si Dev A necesita
cambiarlo, avisa por chat, Dev B hace `git pull` y actualiza mocks.

### Git workflow

- `main` siempre funcional. Nadie rompe `main`.
- Cada dev en su rama: `dev-a/<feature>` y `dev-b/<feature>`.
- **Rebase contra `main` al inicio de cada hora**:
  ```bash
  git fetch origin
  git rebase origin/main
  ```
- Merge a `main` vía PR del dueño. Sin revisión cruzada — confiar en la división.
- **Prohibido** `git push --force` en `main`.
- Usar siempre `git rebase`, nunca `git merge origin/main` — historial lineal.
- Commits frecuentes (cada 30 min idealmente). Mensajes cortos en presente:
  `feat: add geocode tool`, `fix: transit radius query`.

### Timeline (6 horas del evento)

#### Pre-evento (noche anterior, ~1h cada uno, en paralelo)

**Dev A**
- `git submodule update --init --recursive`
- `cd "mcp cesar" && uv sync && uv run python tests/smoke_test.py` → `smoke: OK`
- Crear proyecto Supabase free tier · habilitar PostGIS · correr `setup_schema.sql`
- Descargar GTFS de `datos.cdmx.gob.mx/dataset/gtfs` · extraer `stops.txt` a `data_ingestion/raw/`
- Con el MCP corriendo: `list_datasets(search="sismico")`, `search="inundacion"`,
  `search="agua"`, `search="2017"` — apuntar los slugs reales en `DATASET_SLUGS.md`
- (Opcional) Conseguir `INEGI_TOKEN` para DENUE

**Dev B**
- `npm create vue@latest frontend`
- `cd frontend && npm install axios leaflet @vue-leaflet/vue-leaflet`
- `npm run dev` levanta en localhost:5173 sin errores
- Commit del scaffold limpio a `main`
- Crear `.env` local con `VITE_GATEWAY_URL=http://localhost:8000` y `VITE_MOCK=1`

#### Hora 0:00 — 🔁 Kickoff juntos (30 min)

1. Sync rápido: ambos confirman checklist pre-evento verde.
2. **Pair-edit `API_CONTRACT.md`** (20 min). Se congela al final.
3. Dev A commitea el contract. Dev B hace `git pull` y arranca con mocks.

#### Hora 0:30 → 2:00 — Construcción en paralelo (90 min, aislada)

**Dev A — backend**
1. `gateway/requirements.txt` · `gateway/pyproject.toml`.
2. `gateway/mcp_client.py` — cliente stdio que levanta `cdmx-mcp`.
3. `gateway/tool_registry.py` — une tools remotas + locales.
4. `gateway/tools/geocode.py` — Nominatim con cache en memoria.
5. `gateway/main.py` — `POST /chat` con lifespan que inicia el MCP.
6. `curl -X POST /chat` con una pregunta real responde correctamente.

**Dev B — frontend (todo con mocks)**
1. `frontend/src/composables/useChat.js` — llama a `/chat` (o devuelve fixture si `VITE_MOCK=1`).
2. `frontend/src/composables/useReport.js` — estado del reporte.
3. `frontend/src/components/ChatInterface.vue` — input + historial.
4. `frontend/src/components/ScoreCard.vue` — escala 1–10 (snippet en §"ScoreCard.vue").
5. Vista funcional con el fixture de Narvarte Poniente — **sin backend real todavía**.

#### Hora 2:00 — 🔁 Checkpoint (15 min)

- Dev A hace `curl` en vivo al `/chat`: respuesta matchea el contract.
- Dev B apaga el mock (`VITE_MOCK=0`) y pregunta desde el browser.
- La respuesta real llega y se renderiza. Si no: **se ajusta el código, no el contract.**
- Si Dev A está atrasado: Dev B sigue con mocks. No se bloquea.

#### Hora 2:15 → 4:00 — Completar features

**Dev A**
1. `gateway/tools/transit.py` — `stations_within_radius` via Supabase PostGIS.
2. Módulo de scoring: las 9 fórmulas de §"Las 9 dimensiones" normalizadas a 1–10.
3. `gateway/tools/report.py` — `generate_report()` con Jinja2 para el HTML.
4. System prompt final + enforcement de `generate_report` al cierre.
5. Manejo de `faltantes` + renormalización de pesos.

**Dev B**
1. `frontend/src/components/RiskMap.vue` — Leaflet con marcador en lat/lng.
2. `frontend/src/components/ReportViewer.vue` — `v-html` del reporte HTML.
3. Capas de riesgo sobre el mapa (polígonos de zona sísmica) — si hay tiempo.
4. CSS global: paleta de colores de §"Etiqueta y color por score", tipografía.

#### Hora 4:00 — 🔁 Checkpoint (15 min)

- Demo end-to-end en vivo: Dev B pregunta en Vue, respuesta trae 7+ dimensiones
  con scores 1–10 + reporte HTML + mapa con marcador.
- Si alguna tool no funciona: **se corta**. 5 dimensiones sólidas > 9 flojas.
- Decidir si hay tiempo para el wow factor (capas de mapa, pesos personalizables UI).

#### Hora 4:15 → 5:00 — Pulir

**Dev A**
1. Errores robustos: cada tool fallida va a `faltantes` con motivo legible.
2. Aplicar `preferences.prioridad_weights` en el cálculo global.
3. Respuesta amigable para alcaldías fuera de scope (CUA, BJ, COY).
4. Backup de la DB Supabase (Dashboard → Database → Backups).

**Dev B**
1. `frontend/demo-questions.md` con 3 preguntas de demo (owned by Dev B).
2. Ensayar las 3 preguntas en el browser — ninguna debe fallar.
3. `npm run build` verifica que el bundle carga sin errores.
4. Layout final pulido.

#### Hora 5:00 — 🛑 FREEZE

- **Nadie commitea nuevas features.** Solo fixes críticos del demo.
- Merge de ramas a `main`. Dev A primero, Dev B después.
- `git log --oneline` limpio. Conflicto → `git rebase --abort` y resincronizar por chat.

#### Hora 5:00 → 6:00 — Ensayo + pitch

- 2 corridas completas de las 3 preguntas de demo. Timer a 3 min exactos.
- **Dev A** narra arquitectura (30s): "MCP server abierto → gateway FastAPI → scoring → Claude API".
- **Dev B** maneja el laptop y demuestra (90s).
- Problema (30s) e impacto (30s) los dicen alternados.

### Reglas anti-bloqueo

1. **Si Dev A se atrasa, Dev B NUNCA espera.** Usa los mocks del contract.
2. **Si una tool tarda > 30 min en integrarse, Dev A la corta.** 5 funcionando > 9 rotas.
3. **Claude Code es el tercer integrante.** Generar scaffolds, normalizadores, componentes — no escribir boilerplate a mano.
4. **Nunca demostrar algo no probado 3 veces.**
5. **Cambios al contract = aviso explícito por chat + `git pull` inmediato.**
6. **El mapa es opcional, el chat no.** Si faltan 30 min, corta el mapa.
7. **No abrir el laptop del otro.** Nunca. El checkpoint es el único momento presencial.

### Canal de comunicación

- **Chat (WhatsApp/Slack):** cambios al contract, avisos de merge a `main`, pedir ayuda.
- **Presencial (checkpoints cada hora):** sync de status, demo en vivo, decisiones de scope.
- Fuera de esos dos canales, cada uno trabaja en su directorio en silencio.
