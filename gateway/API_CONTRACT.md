# API_CONTRACT — `POST /chat`

**Owner:** Dev A · **Status:** DRAFT hasta que los 2 devs digan "congelado".
Una vez congelado, cualquier cambio requiere aviso explícito por chat y
`git pull` inmediato del otro dev.

Este es el único acoplamiento entre `frontend/` y `gateway/`. Dev B trabaja
100% con mocks basados en el fixture de §6 mientras Dev A construye el gateway.

---

## 1. Endpoint

```
POST /chat
Content-Type: application/json
```

CORS habilitado para `http://localhost:5173` (Vite dev server).
Sin auth. Sin streaming en MVP (respuesta sincrónica).
Timeout sugerido en el cliente: **60 s** (las llamadas encadenadas a Claude
+ tools pueden tardar 15–40 s).

---

## 2. Request

```ts
interface ChatRequest {
  messages: Message[];          // historial completo (ver §3)
  preferences?: Preferences;    // opcional
}

interface Message {
  role: "user" | "assistant";
  content: string | MessageBlock[];   // string para input del usuario, array opaco para eco del gateway
}

interface Preferences {
  idioma?: "es" | "en";         // default "es"
  prioridad_weights?: {          // pesos personalizados 0–100 por dimensión
    [dimension_id: string]: number;
  };
}
```

Ejemplo mínimo:
```json
{
  "messages": [
    { "role": "user", "content": "¿Es buena zona para vivir Narvarte Poniente?" }
  ],
  "preferences": { "idioma": "es" }
}
```

Con pesos personalizados:
```json
{
  "messages": [...],
  "preferences": {
    "idioma": "es",
    "prioridad_weights": { "seguridad": 30, "agua": 25, "transporte": 20 }
  }
}
```

---

## 3. Historial (`messages`) — regla de oro

El array `messages` es **opaco para Dev B**. Reglas:

1. Para agregar un turno nuevo: Dev B hace `messages.push({role:"user", content:"..."})` y envía todo el array al gateway.
2. La respuesta trae `messages` actualizado (incluye el `{role:"assistant"}` nuevo y posibles bloques internos de tool use). Dev B lo **sobrescribe** en su estado.
3. **Nunca** mutar, filtrar, ni inspeccionar `content` si es un array — el gateway necesita los bloques `tool_use`/`tool_result` intactos para la continuación.
4. Para mostrar texto al usuario, Dev B usa el campo `text` de la respuesta (§4), no escarba en `messages`.

---

## 4. Response

```ts
interface ChatResponse {
  messages: Message[];          // historial actualizado — Dev B lo guarda tal cual
  text: string;                 // texto markdown del último turno del asistente (para la burbuja del chat)
  report: Report | null;        // no-null solo si este turno produjo un reporte
  map: MapData | null;          // no-null solo si se geocodificó una dirección
  error: ApiError | null;       // no-null si hubo error irrecuperable
}

interface Report {
  direccion: string;                                    // texto legible ("Narvarte Poniente, BJ")
  coords: { lat: number; lng: number };
  global: { score: number; etiqueta: EtiquetaScore };
  dimensiones: Dimension[];
  faltantes: { id: DimensionId; razon: string }[];
  html: string;                                         // artefacto completo, Dev B lo renderiza con v-html
}

interface Dimension {
  id: DimensionId;
  nombre: string;                // "Seguridad"
  score: number;                 // 1.0–10.0
  peso_aplicado: number;         // 0–100, ya renormalizado
  fuente: string;                // "FGJ CDMX — carpetas de investigación"
  dataset_id: string | null;     // "fgj" · "atlas-de-riesgo-sismico" · null para tools internas
  consultado_en: string;         // YYYY-MM-DD
  dato_bruto: string;            // "48 delitos / 1000 hab últimos 12m"
  detalle: string;               // frase adicional de contexto
}

type DimensionId =
  | "seguridad"
  | "aire"
  | "sismico"
  | "inundacion"
  | "agua"
  | "transporte"
  | "integridad_2017"
  | "servicios"
  | "ecobici";

type EtiquetaScore =
  | "Excelente"    // 8.5–10.0
  | "Bueno"        // 7.0–8.4
  | "Aceptable"    // 5.5–6.9
  | "Preocupante"  // 4.0–5.4
  | "Evitar";      // 1.0–3.9

interface MapData {
  center: { lat: number; lng: number };
  zoom: number;                                 // sugerido, Dev B puede ignorar
  marker: { lat: number; lng: number; popup: string };
  stations: {
    lat: number; lng: number;
    nombre: string;
    modo: "metro" | "metrobus" | "rtp" | "trolebus" | "cablebus" | "bus";
    distancia_m: number;
  }[];
}

interface ApiError {
  code: "geocode_failed" | "out_of_scope" | "internal";
  message: string;    // legible para mostrar al usuario
}
```

Reglas adicionales:
- Si `report` es `null`, Dev B solo muestra `text` (típico en primera interacción de aclaración).
- Si `map` es `null`, Dev B oculta `RiskMap.vue`.
- Si `error` es non-null, Dev B muestra `error.message` en lugar del reporte.
- `dimensiones` **nunca** contiene las que están en `faltantes` — son mutuamente exclusivas.
- `peso_aplicado` ya está renormalizado: la suma de pesos en `dimensiones` es 100.

---

## 5. Pesos default (si `prioridad_weights` no viene)

| `id` | peso default |
|---|---|
| `seguridad` | 20 |
| `sismico` | 18 |
| `agua` | 14 |
| `transporte` | 14 |
| `aire` | 12 |
| `inundacion` | 8 |
| `integridad_2017` | 8 |
| `servicios` | 4 |
| `ecobici` | 2 |

Si una dimensión cae a `faltantes`, su peso se redistribuye proporcionalmente
entre las dimensiones que sí se calcularon (renormalización).

---

## 6. Fixture de ejemplo — Narvarte Poniente

Dev B puede usar este JSON como mock mientras el gateway no existe.
Guárdalo en `frontend/src/mocks/chat.narvarte.json` (owned por Dev B).

```json
{
  "messages": [
    { "role": "user", "content": "¿Es buena zona para vivir Narvarte Poniente?" },
    { "role": "assistant", "content": "[bloques opacos de Claude con tool_use/tool_result]" }
  ],
  "text": "Narvarte Poniente es una zona **bueno** para vivir (7.3/10). Destaca por buen acceso a transporte y servicios, con tradeoffs en calidad del aire y riesgo sísmico medio. Se consultaron 8 de 9 fuentes de gobierno.",
  "report": {
    "direccion": "Narvarte Poniente, Benito Juárez, CDMX",
    "coords": { "lat": 19.3885, "lng": -99.1574 },
    "global": { "score": 7.3, "etiqueta": "Bueno" },
    "dimensiones": [
      {
        "id": "seguridad",
        "nombre": "Seguridad",
        "score": 6.8,
        "peso_aplicado": 20.4,
        "fuente": "FGJ CDMX — carpetas de investigación",
        "dataset_id": "fgj",
        "consultado_en": "2026-04-18",
        "dato_bruto": "42 delitos / 1000 hab últimos 12 meses",
        "detalle": "Por debajo de la mediana de la alcaldía Benito Juárez"
      },
      {
        "id": "sismico",
        "nombre": "Riesgo sísmico",
        "score": 5.5,
        "peso_aplicado": 18.4,
        "fuente": "Atlas de Riesgo CDMX — Sísmico",
        "dataset_id": "atlas-de-riesgo-sismico",
        "consultado_en": "2026-04-18",
        "dato_bruto": "Zona II — suelo de transición",
        "detalle": "No se encuentra en polígono de Zona Cero 2017"
      },
      {
        "id": "agua",
        "nombre": "Confiabilidad del agua",
        "score": 7.4,
        "peso_aplicado": 14.3,
        "fuente": "SACMEX — Reportes de agua 2022-2024",
        "dataset_id": "reportes-de-agua",
        "consultado_en": "2026-04-18",
        "dato_bruto": "12 reportes en últimos 6 meses por 1000 hab",
        "detalle": "Debajo del percentil 30 de CDMX"
      },
      {
        "id": "transporte",
        "nombre": "Acceso a transporte",
        "score": 8.2,
        "peso_aplicado": 14.3,
        "fuente": "GTFS CDMX · SEMOVI",
        "dataset_id": null,
        "consultado_en": "2026-04-18",
        "dato_bruto": "14 paradas RTP en 800 m",
        "detalle": "Nota: feed MVP solo incluye RTP; Metro/Metrobús no contabilizados"
      },
      {
        "id": "aire",
        "nombre": "Calidad del aire",
        "score": 5.8,
        "peso_aplicado": 12.2,
        "fuente": "SIMAT — estación Benito Juárez",
        "dataset_id": null,
        "consultado_en": "2026-04-18",
        "dato_bruto": "PM2.5 promedio 7d: 23 µg/m³",
        "detalle": "Por encima de la recomendación OMS (12 µg/m³)"
      },
      {
        "id": "inundacion",
        "nombre": "Riesgo de inundación",
        "score": 8.5,
        "peso_aplicado": 8.2,
        "fuente": "Atlas de Riesgo CDMX — Inundaciones",
        "dataset_id": "atlas-de-riesgo-inundaciones",
        "consultado_en": "2026-04-18",
        "dato_bruto": "Nivel bajo para Benito Juárez",
        "detalle": "Sin eventos críticos registrados en el polígono"
      },
      {
        "id": "integridad_2017",
        "nombre": "Integridad estructural 2017",
        "score": 7.0,
        "peso_aplicado": 8.2,
        "fuente": "Atlas Zona Cero 2017",
        "dataset_id": "atlas-de-riesgo-zona-cero-2017",
        "consultado_en": "2026-04-18",
        "dato_bruto": "3 inmuebles afectados en 300 m",
        "detalle": "Zona colindante con polígono crítico"
      },
      {
        "id": "servicios",
        "nombre": "Servicios cercanos",
        "score": 9.0,
        "peso_aplicado": 4.1,
        "fuente": "DENUE — INEGI",
        "dataset_id": null,
        "consultado_en": "2026-04-18",
        "dato_bruto": "Super · farmacia · escuela · hospital cubiertos en 800 m",
        "detalle": "Cobertura completa de las 4 categorías clave"
      }
    ],
    "faltantes": [
      { "id": "ecobici", "razon": "GBFS no devolvió cicloestaciones en 500 m" }
    ],
    "html": "<article class='report'><h1>Narvarte Poniente</h1><p>Score global: <strong>7.3/10 — Bueno</strong></p>...</article>"
  },
  "map": {
    "center": { "lat": 19.3885, "lng": -99.1574 },
    "zoom": 15,
    "marker": {
      "lat": 19.3885,
      "lng": -99.1574,
      "popup": "Narvarte Poniente, BJ"
    },
    "stations": [
      { "lat": 19.3901, "lng": -99.1555, "nombre": "Etiopía / Plaza de la Transparencia", "modo": "rtp", "distancia_m": 220 },
      { "lat": 19.3867, "lng": -99.1601, "nombre": "Eje 5 Sur - Gabriel Mancera", "modo": "rtp", "distancia_m": 340 },
      { "lat": 19.3923, "lng": -99.1552, "nombre": "Diagonal San Antonio", "modo": "rtp", "distancia_m": 510 }
    ]
  },
  "error": null
}
```

---

## 7. Errores — shape normalizado

Si el gateway no puede contestar (fuera de MVP, geocode falla, etc.) devuelve
HTTP 200 con `error` non-null (para que Dev B maneje UI sin excepciones):

```json
{
  "messages": [...],
  "text": "No encontré esa dirección. ¿Puedes darme la colonia y alcaldía?",
  "report": null,
  "map": null,
  "error": {
    "code": "geocode_failed",
    "message": "Nominatim no devolvió match para la búsqueda."
  }
}
```

Códigos:
- `geocode_failed` — dirección no parseable.
- `out_of_scope` — alcaldía fuera de Cuauhtémoc / Benito Juárez / Coyoacán.
- `internal` — cualquier otra cosa (timeout, MCP caído).

HTTP 5xx solo si el gateway mismo crashea.

---

## 8. Endpoint de salud (útil para debugging)

```
GET /health
→ 200 {"status": "ok", "mcp": "connected", "supabase": "ok"}
```

No parte del contrato del chat, pero Dev B puede pingearlo desde la consola
del browser para verificar que el gateway está vivo.

---

## 9. Cambios a este contrato

1. Quien quiere cambiar algo **avisa en chat antes de commitear**.
2. El otro dev hace `git pull` y actualiza su lado (mocks o endpoint).
3. Si no hay tiempo para sincronizar: **no se cambia**, se trabaja con lo que hay.

---

**Status actual:** `DRAFT`
**Firmas para congelar:** Dev A [ ] · Dev B [ ]
