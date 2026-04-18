"""
Gateway FastAPI — ColonIA
Versión real con:
  - Claude API (tool use loop)
  - Tavily Search (contexto web enriquecido por colonia)
  - Respuestas específicas por consulta del usuario
  - Fallback gracioso al fixture si algo falla

Correr:
    cd gateway
    python -m venv .venv
    source .venv/bin/activate   (mac/linux)
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
import asyncio
from datetime import date
from typing import Optional, List, Tuple
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import anthropic
from tools.tavily_search import search_neighborhood_context, TAVILY_TOOL_DEFINITION

load_dotenv()

# ─── Constantes ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-5"
TODAY = date.today().isoformat()

# Pesos default de dimensiones
DEFAULT_WEIGHTS = {
    "seguridad": 20,
    "sismico": 18,
    "agua": 14,
    "transporte": 14,
    "aire": 12,
    "inundacion": 8,
    "integridad_2017": 8,
    "servicios": 4,
    "ecobici": 2,
}

# ─── App ────────────────────────────────────────────────────────────────────
app = FastAPI(title="ColonIA gateway", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Modelos ────────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str
    reportData: Optional[dict] = None


class ChatRequest(BaseModel):
    messages: List[Message]
    preferences: Optional[dict] = None


# ─── System prompt ──────────────────────────────────────────────────────────
def build_system_prompt(preferences: dict | None) -> str:
    weights = DEFAULT_WEIGHTS.copy()
    if preferences and "prioridad_weights" in preferences:
        weights.update(preferences["prioridad_weights"])

    return f"""Eres ColonIA, un agente experto en calidad de vida urbana en CDMX.
Ayudas a personas a evaluar colonias y direcciones con datos objetivos y contexto real.

Hoy es {TODAY}.

## Proceso de evaluación (en orden estricto):

1. **Detecta la colonia/dirección** del mensaje del usuario.

2. **Busca contexto web específico** con search_web_context:
   - Busca "{{}}_seguridad_CDMX" para seguridad e incidentes recientes
   - Busca "{{}}_servicios_noticias" para cambios de infraestructura
   - Busca "{{}}_opinion_vivir" para experiencias de residentes
   Sustituye {{}} con el nombre real de la colonia.

3. **Evalúa las 9 dimensiones** con el contexto obtenido:

   | id | nombre | Fuente principal | Fórmula 1-10 |
   |---|---|---|---|
   | seguridad | Seguridad | FGJ CDMX (carpetas de investigación) | Alto crimen=1, bajo=10 |
   | aire | Calidad del Aire | SIMAT (estaciones de monitoreo) | PM2.5: <12=10, >55=1 |
   | sismico | Riesgo Sísmico | Atlas Riesgo CDMX | Zona I=10, II=6, III=2 |
   | inundacion | Riesgo Inundación | Atlas Riesgo CDMX | Bajo=10, muy alto=1 |
   | agua | Confiabilidad Agua | SACMEX (reportes) | Pocos reportes=10 |
   | transporte | Transporte Público | GTFS CDMX | Más estaciones=mejor |
   | integridad_2017 | Integridad 2017 | Plataforma CDMX (sismo 2017) | Sin daños=10 |
   | servicios | Servicios Cercanos | DENUE INEGI | Cobertura completa=10 |
   | ecobici | ECOBICI | GBFS ECOBICI | ≥4 cicloestaciones=10 |

4. **Pesos aplicados** (default, ajustables por usuario):
{json.dumps(weights, ensure_ascii=False, indent=3)}

5. **Calcula el score global** como promedio ponderado.

6. **Genera el reporte** llamando a generate_final_report con el JSON completo.

## Reglas críticas:
- NUNCA inventes números. Si no tienes dato, la dimensión va a `faltantes`.
- El contexto de Tavily te da información cualitativa reciente — úsalo para el detalle.
- El resumen debe ser específico a LA COLONIA preguntada, nunca genérico.
- Si la pregunta no es sobre una colonia/zona, responde normalmente sin generar reporte.
- Cobertura MVP: Cuauhtémoc, Benito Juárez, Coyoacán, Miguel Hidalgo, Tlalpan, Xochimilco, Iztapalapa. Fuera de eso, avisa y da la alcaldía más cercana.
"""


# ─── Tool: generate_final_report ────────────────────────────────────────────
REPORT_TOOL_DEFINITION = {
    "name": "generate_final_report",
    "description": (
        "Genera el reporte final estructurado de evaluación de una colonia. "
        "Llama a esta tool SIEMPRE al final, dopo de haber buscado contexto web "
        "y evaluado las dimensiones."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "direccion": {"type": "string", "description": "Colonia o dirección evaluada"},
            "lat": {"type": "number", "description": "Latitud del centro de la colonia"},
            "lng": {"type": "number", "description": "Longitud del centro de la colonia"},
            "dimensiones": {
                "type": "array",
                "description": "Lista de dimensiones evaluadas",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "nombre": {"type": "string"},
                        "score": {"type": "number"},
                        "peso_aplicado": {"type": "number"},
                        "fuente": {"type": "string"},
                        "dataset_id": {"type": "string"},
                        "consultado_en": {"type": "string"},
                        "dato_bruto": {"type": "string"},
                        "detalle": {"type": "string"},
                    },
                    "required": ["id", "nombre", "score", "peso_aplicado", "fuente",
                                 "consultado_en", "dato_bruto", "detalle"]
                }
            },
            "faltantes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "razon": {"type": "string"}
                    }
                }
            },
            "resumen_html": {
                "type": "string",
                "description": "Resumen ejecutivo en HTML. Empieza con <h3> y usa <p>, <strong>. Sin CSS inline."
            }
        },
        "required": ["direccion", "lat", "lng", "dimensiones", "faltantes", "resumen_html"]
    }
}


def process_report(args: dict, preferences: dict | None) -> dict:
    """Calcula el score global y arma el ReportData completo."""
    dimensiones = args["dimensiones"]
    faltantes = args.get("faltantes", [])

    # Calcular score global ponderado
    user_weights = {}
    if preferences and "prioridad_weights" in preferences:
        user_weights = preferences["prioridad_weights"]

    total_peso = sum(d["peso_aplicado"] for d in dimensiones)
    if total_peso == 0:
        total_peso = 1

    score_global = sum(
        d["score"] * d["peso_aplicado"] for d in dimensiones
    ) / total_peso

    # Etiqueta
    if score_global >= 8.5:
        etiqueta = "Excelente"
    elif score_global >= 7.0:
        etiqueta = "Bueno"
    elif score_global >= 5.5:
        etiqueta = "Aceptable"
    elif score_global >= 4.0:
        etiqueta = "Preocupante"
    else:
        etiqueta = "Evitar"

    return {
        "direccion": args["direccion"],
        "lat": args["lat"],
        "lng": args["lng"],
        "scores": {
            "global": round(score_global, 1),
            "etiqueta_global": etiqueta,
            "dimensiones": dimensiones,
            "faltantes": faltantes,
        },
        "resumen": args["resumen_html"],
    }


# ─── Tool dispatch ──────────────────────────────────────────────────────────
async def dispatch_tool(name: str, args: dict, preferences: Optional[dict]) -> Tuple[str, Optional[dict]]:
    """
    Ejecuta una tool y devuelve (result_text, report_data_or_none).
    """
    if name == "search_web_context":
        result = await search_neighborhood_context(args["query"])
        return result, None

    elif name == "generate_final_report":
        report = process_report(args, preferences)
        return "Reporte generado correctamente.", report

    return f"Tool desconocida: {name}", None


# ─── Claude tool-use loop ───────────────────────────────────────────────────
async def run_claude_loop(
    user_messages: List[dict],
    preferences: Optional[dict],
) -> Tuple[str, Optional[dict]]:
    """
    Ejecuta el loop de tool-use de Claude.
    Devuelve (texto_respuesta, report_data_or_none).
    """
    if not ANTHROPIC_API_KEY:
        return "⚠ ANTHROPIC_API_KEY no configurada en el servidor.", None

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tools = [TAVILY_TOOL_DEFINITION, REPORT_TOOL_DEFINITION]

    messages = [{"role": m["role"], "content": m["content"]} for m in user_messages]
    system = build_system_prompt(preferences)

    report_data = None
    final_text = ""

    # Máximo 10 iteraciones de tool-use
    for _ in range(10):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )

        # Acumular texto de esta respuesta
        text_blocks = [b.text for b in response.content if b.type == "text"]
        if text_blocks:
            final_text = " ".join(text_blocks)

        # Si terminó sin más tools → salir
        if response.stop_reason == "end_turn":
            break

        # Procesar tool calls
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            break

        # Agregar respuesta del asistente al historial
        messages.append({"role": "assistant", "content": response.content})

        # Ejecutar todas las tools (en paralelo si son varias)
        tool_results = []
        tasks = [dispatch_tool(tc.name, tc.input, preferences) for tc in tool_calls]
        results = await asyncio.gather(*tasks)

        for tc, (result_text, rpt) in zip(tool_calls, results):
            if rpt:
                report_data = rpt  # capturar el reporte cuando aparezca
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})

    return final_text or "Evaluación completada.", report_data


# ─── Endpoints ──────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "claude": "connected" if ANTHROPIC_API_KEY else "missing_key",
        "tavily": "connected" if os.getenv("TAVILY_API_KEY") else "missing_key",
        "version": "0.2.0",
    }


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    user_msgs = [
        {"role": m.role, "content": m.content}
        for m in req.messages
        if m.role in ("user", "assistant") and isinstance(m.content, str)
    ]

    try:
        content_text, report_data = await run_claude_loop(user_msgs, req.preferences)
    except Exception as e:
        return {
            "messages": [m.model_dump() for m in req.messages],
            "content": "Ocurrió un error procesando tu consulta. Intenta de nuevo.",
            "reportData": None,
            "error": {"code": "internal", "message": str(e)},
        }

    new_messages = [m.model_dump() for m in req.messages]
    new_messages.append({
        "role": "assistant",
        "content": content_text,
        "reportData": report_data,
    })

    return {
        "messages": new_messages,
        "content": content_text,
        "reportData": report_data,
        "error": None,
    }
