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
