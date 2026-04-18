# API_CONTRACT — `POST /chat`

**Owner:** Dev A · **Status:** DRAFT hasta que los 2 devs firmen en §9.
Una vez firmado, cualquier cambio requiere aviso explícito por chat y
`git pull` inmediato del otro lado.

Este es el único acoplamiento entre `frontend/` y `gateway/`. Dev B trabaja
100% con mocks basados en §6 mientras Dev A construye el gateway.

> **Alineado con el mock que ya está en `frontend/src/composables/useChat.js`**
> — si este contrato y esa implementación divergen, **esta fuente manda**.

---

## 1. Endpoint

```
POST /chat
Content-Type: application/json
```

CORS habilitado para `http://localhost:5173` (Vite dev server).
Sin auth. Sin streaming en MVP (respuesta sincrónica).
Timeout sugerido en el cliente: **60 s** (el tool-use loop puede tardar 15–40 s).

---

## 2. Request

```ts
interface ChatRequest {
  messages: Message[];          // historial completo (ver §3)
  preferences?: Preferences;    // opcional
}

interface Message {
  role: "user" | "assistant";
  content: string;              // texto del turno (Dev B solo envía strings)
  reportData?: ReportData;      // presente solo en turnos del asistente previos (puede ir de vuelta al gateway)
}

interface Preferences {
  idioma?: "es" | "en";         // default "es"
  prioridad_weights?: {         // pesos personalizados 0–100 por dimension_id
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

## 3. Historial de conversación

El array `messages` lleva turnos en formato simple:
- `{role:"user", content:"texto"}` para input humano.
- `{role:"assistant", content:"texto visible", reportData?:…}` para respuestas previas.

Para multi-turno: Dev B agrega el nuevo user message, envía todo el array.
El gateway devuelve el mismo array + el nuevo turno del asistente.

> El gateway internamente mantiene el historial en formato Anthropic
> (con bloques `tool_use`/`tool_result`) pero **no los expone** a Dev B.
> La traducción pasa a strings puros antes de responder.

---

## 4. Response

```ts
interface ChatResponse {
  messages: Message[];      // historial actualizado — Dev B lo sobrescribe tal cual
  content: string;          // texto visible del último turno del asistente (markdown)
  reportData: ReportData | null;   // no-null solo si este turno produjo un reporte
  error: ApiError | null;   // no-null si hubo error manejado
}

interface ReportData {
  direccion: string;        // "Narvarte Poniente, Ciudad de México"
  lat: number;              // centro para RiskMap.vue
  lng: number;
  scores: Scores;
  resumen: string;          // HTML del resumen ejecutivo (Dev B lo renderiza con v-html)
  stations?: Station[];     // OPCIONAL — estaciones cerca; futuro para marcar en el mapa
}

interface Scores {
  global: number;                       // 1.0–10.0
  etiqueta_global: EtiquetaScore;
  dimensiones: Dimension[];
  faltantes: Faltante[];
}

interface Dimension {
  id: DimensionId;
  nombre: string;           // "Seguridad" (en español, título)
  score: number;            // 1.0–10.0
  peso_aplicado: number;    // 0–100, ya renormalizado (la suma de dimensiones es 100)
  fuente: string;           // "FGJ CDMX — carpetas de investigación"
  dataset_id: string | null;// slug CKAN real o null para tools que no pasan por CKAN
  consultado_en: string;    // YYYY-MM-DD
  dato_bruto: string;       // "48 delitos / 1000 hab últimos 12m"
  detalle: string;          // frase de contexto
}

interface Faltante {
  id: DimensionId;
  razon: string;            // "GBFS no devolvió cicloestaciones en 500 m"
}

interface Station {         // opcional; el mapa actual solo usa lat/lng del reporte
  lat: number; lng: number;
  nombre: string;
  modo: "metro" | "metrobus" | "rtp" | "trolebus" | "cablebus" | "bus";
  distancia_m: number;
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

interface ApiError {
  code: "geocode_failed" | "out_of_scope" | "internal";
  message: string;    // legible, Dev B lo puede mostrar al usuario
}
```

Reglas adicionales:
- Si `reportData` es `null`, Dev B solo muestra `content` (típico en aclaraciones).
- Si `error` es non-null, Dev B muestra `error.message`. HTTP sigue siendo 200.
- `dimensiones` y `faltantes` son **mutuamente exclusivas** — una dimensión está en una u otra, nunca en las dos.
- `peso_aplicado` ya viene renormalizado: `sum(dimensiones.peso_aplicado) === 100`.
- `resumen` llega como HTML. Convención: empieza con `<h3>` y usa `<p>`, `<strong>`. Sin CSS inline (Dev B ya lo estiliza con `.resume-box :deep(h3)`).
- **Stations** en `reportData` es opcional; en MVP no se requiere — `RiskMap` actual solo usa `lat`/`lng`.

---

## 5. Pesos default (si `preferences.prioridad_weights` no viene)

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

Si una dimensión cae a `faltantes`, el gateway **redistribuye su peso**
proporcionalmente entre las dimensiones activas.

---

## 6. Fixture de ejemplo — Narvarte Poniente

El mock actual en `frontend/src/composables/useChat.js` (`MOCK_RESPONSE`) es la
**fuente de verdad** del fixture. Shape esperado de la response completa:

```json
{
  "messages": [
    { "role": "user", "content": "¿Es buena zona para vivir Narvarte Poniente?" },
    { "role": "assistant", "content": "Aquí tienes la evaluación del lugar:", "reportData": { "...": "..." } }
  ],
  "content": "Aquí tienes la evaluación del lugar:",
  "reportData": {
    "direccion": "Narvarte Poniente, Ciudad de México",
    "lat": 19.3934,
    "lng": -99.155,
    "scores": {
      "global": 7.6,
      "etiqueta_global": "Bueno",
      "dimensiones": [
        {
          "id": "seguridad",
          "nombre": "Seguridad",
          "score": 7.8,
          "peso_aplicado": 20,
          "fuente": "FGJ CDMX",
          "dataset_id": "fgj",
          "consultado_en": "2026-04-18",
          "dato_bruto": "48 delitos / 1000 hab últimos 12m",
          "detalle": "Tendencia estable vs. trimestre previo"
        }
      ],
      "faltantes": [
        { "id": "ecobici", "razon": "GBFS no devolvió cicloestaciones en 500 m" }
      ]
    },
    "resumen": "<h3>Resumen Ejecutivo: Narvarte Poniente</h3><p>Evaluación...</p>"
  },
  "error": null
}
```

---

## 7. Errores — HTTP 200 con `error` non-null

Cuando el gateway no puede completar (fuera de MVP, geocode falla, etc.):

```json
{
  "messages": [...],
  "content": "No encontré esa dirección. ¿Puedes darme la colonia y alcaldía?",
  "reportData": null,
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

HTTP 5xx solo si el gateway mismo crashea (proceso muerto).

---

## 8. Endpoint de salud

```
GET /health
→ 200 {"status": "ok", "mcp": "connected", "supabase": "ok"}
```

Para que Dev B verifique desde devtools que el gateway está vivo.

---

## 9. Cambios a este contrato

1. Quien quiere cambiar algo **avisa en chat antes de commitear**.
2. El otro dev hace `git pull` y actualiza su lado (mocks o endpoint).
3. Si no hay tiempo: **no se cambia**, se trabaja con lo que hay.

---

## 10. Firmas para congelar

Cuando ambos devs estén de acuerdo con este documento, poner la fecha en su firma:

- **Dev A:** [ ] firmado (YYYY-MM-DD HH:MM)
- **Dev B:** [ ] firmado (YYYY-MM-DD HH:MM)

Mientras haya un `[ ]` sin llenar, el estado es `DRAFT`.
