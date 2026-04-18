"""
Gateway FastAPI — Claude con tool use + cdmx-mcp + tools locales.

Claude decide qué tools llamar según la pregunta:
- "Roma Norte" → compute_location_score → reportData completo
- "¿cómo está el aire en Polanco?" → air_quality_now → solo texto
- "¿es seguro el Centro?" → crime_hotspots → solo texto
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from markdown_it import MarkdownIt
from pydantic import BaseModel

_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True}).enable("table")


def markdown_to_html(text: str) -> str:
    """Convierte markdown a HTML seguro para v-html en Vue."""
    if not text:
        return ""
    return _md.render(text)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from mcp_client import CdmxMcpClient
from tools.geocode import geocode_address
from tools.report_builder import compute_location_score
from tools.transit import get_transit_access

MODEL = "claude-sonnet-4-5"

# ─────────────────── lifespan: arrancar/apagar el MCP ───────────────────

mcp: CdmxMcpClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp
    mcp = CdmxMcpClient()
    try:
        await mcp.connect()
        print("[gateway] cdmx-mcp conectado")
    except Exception as e:
        print(f"[gateway] FALLÓ conexión MCP: {e}")
        mcp = None
    yield
    if mcp:
        await mcp.close()
        print("[gateway] cdmx-mcp cerrado")


app = FastAPI(title="ColonIA gateway", version="0.5.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str
    content: Any
    reportData: dict | None = None


class ChatRequest(BaseModel):
    messages: list[Message]
    preferences: dict | None = None


# ─────────────────── Tools LOCALES expuestas a Claude ───────────────────

LOCAL_TOOLS = [
    {
        "name": "compute_location_score",
        "description": (
            "Evalúa una dirección o colonia de CDMX de forma integral. Devuelve "
            "scores 1–10 por seguridad, aire, riesgo sísmico, inundación, agua "
            "y transporte + coordenadas. USA ESTA TOOL cuando el usuario pregunta "
            "si una colonia/dirección es buena para vivir, o pide un reporte completo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "direccion": {
                    "type": "string",
                    "description": "Colonia, dirección o punto de referencia en CDMX",
                }
            },
            "required": ["direccion"],
        },
    },
    {
        "name": "geocode_address",
        "description": (
            "Convierte una dirección de CDMX a lat/lng + alcaldía + colonia. "
            "Úsala cuando necesites ubicar un lugar para otra consulta específica."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"direccion": {"type": "string"}},
            "required": ["direccion"],
        },
    },
    {
        "name": "get_transit_access",
        "description": (
            "Paradas de transporte público (Metro/Metrobús/RTP) en un radio desde "
            "un punto lat/lng. Úsala solo para preguntas específicas de transporte."
        ),
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
]

SYSTEM_PROMPT = """\
Eres **ColonIA**, un agente experto en calidad de vida urbana en la Ciudad de México.
Ayudas a personas a evaluar colonias/direcciones usando datos abiertos de gobierno.

Tools disponibles:
- compute_location_score(direccion): EVALUACIÓN COMPLETA de una colonia (9 dimensiones + mapa).
- geocode_address(direccion): solo coordenadas.
- get_transit_access(lat, lng, radio_m): paradas de transporte cerca.
- crime_hotspots(year, alcaldia, top_n): delitos FGJ por alcaldía.
- air_quality_now(zone?, limit?): calidad del aire SIMAT.
- query_records(dataset_id, where, ...): consultas CKAN. Slugs: "atlas-de-riesgo-sismico", "atlas-de-riesgo-inundaciones", "reportes-de-agua".
- otras tools del MCP como `list_datasets`, `describe_dataset`, `aggregate`.

Reglas de decisión:
1. **Si el usuario menciona una colonia/dirección SIN pregunta específica** (ej: "Roma Norte", "vivo en Narvarte") → llama compute_location_score INMEDIATAMENTE. No preguntes antes.
2. **Si pide análisis/evaluación completa** ("¿es buena?", "¿dónde vivir?", "analiza X", "quiero el análisis completo") → compute_location_score.
3. **Si pregunta algo específico** (solo aire / solo seguridad / solo inundación / solo transporte) → usa la tool puntual correspondiente. NO llames compute_location_score.
4. "donde vivo", "mi casa" sin ubicación previa → pregunta la dirección. Si ya la dio antes en la conversación, úsala.
5. Menciona la fuente de gobierno al explicar (FGJ, SIMAT, SACMEX, Atlas de Riesgo).
6. NO inventes números.

Formato de salida (IMPORTANTE):
- Escribe en **markdown** (será renderizado a HTML en el frontend).
- Usa `## Títulos` con moderación, `**negritas**` para puntos clave, listas con `-`, separadores `---` entre secciones mayores.
- Puedes usar tablas markdown (`| col | col |`).
- Párrafos separados por doble salto de línea.
- Mantén respuestas **concisas** (máximo 3-4 párrafos cortos o una tabla con 4-6 filas).
- NO uses frases introductorias largas ("¡Hola! Veo que...") — ve directo al grano.
"""


# ─────────────────── Dispatcher ───────────────────

async def dispatch_tool(name: str, arguments: dict) -> tuple[str, dict | None]:
    """
    Ejecuta una tool. Devuelve (texto_para_claude, reportData_si_aplica).
    """
    # --- locales ---
    if name == "compute_location_score":
        report = await compute_location_score(arguments.get("direccion", ""), mcp)
        if report.get("__error__") == "geocode_failed":
            return (
                f"No pude geocodificar «{arguments.get('direccion')}». "
                "Pídele al usuario una dirección o colonia más específica.",
                None,
            )
        # Texto resumen para Claude (JSON compacto)
        summary = {
            "direccion": report["direccion"],
            "lat": report["lat"], "lng": report["lng"],
            "global": report["scores"]["global"],
            "etiqueta_global": report["scores"]["etiqueta_global"],
            "dimensiones": [
                {"id": d["id"], "score": d["score"], "dato_bruto": d["dato_bruto"]}
                for d in report["scores"]["dimensiones"]
            ],
            "faltantes": [f["id"] for f in report["scores"]["faltantes"]],
        }
        return json.dumps(summary, ensure_ascii=False), report

    if name == "geocode_address":
        r = geocode_address(arguments.get("direccion", ""))
        return (json.dumps(r, ensure_ascii=False) if r else "No encontrada"), None

    if name == "get_transit_access":
        r = get_transit_access(
            float(arguments["lat"]), float(arguments["lng"]),
            radio_m=int(arguments.get("radio_m", 800)),
        )
        return json.dumps(r, ensure_ascii=False), None

    # --- MCP (cualquier otra tool) ---
    if mcp is None:
        return "Error: servidor MCP no está disponible.", None
    try:
        text = await mcp.call_tool(name, arguments)
        return text, None
    except Exception as e:
        return f"Error ejecutando {name}: {e}", None


# ─────────────────── Endpoints ───────────────────

@app.get("/health")
async def health() -> dict:
    mcp_status = "connected" if mcp and mcp.session else "disconnected"
    return {"status": "ok", "mcp": mcp_status, "supabase": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Construir lista de tools: locales + MCP
    tools_list = list(LOCAL_TOOLS)
    if mcp:
        try:
            mcp_tools = await mcp.list_tools()
            # Filtrar para evitar conflictos de nombre y caché interno
            for t in mcp_tools:
                if t["name"] not in {lt["name"] for lt in LOCAL_TOOLS}:
                    tools_list.append(t)
        except Exception as e:
            print(f"[gateway] list_tools error: {e}")

    # Convertir historial a formato Anthropic
    anthropic_messages = []
    for m in req.messages:
        if isinstance(m.content, str):
            anthropic_messages.append({"role": m.role, "content": m.content})
        else:
            # contenido ya estructurado (echo previo del gateway)
            anthropic_messages.append({"role": m.role, "content": m.content})

    final_report: dict | None = None

    # Loop de tool-use
    for _iter in range(10):  # hard limit de iteraciones
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=tools_list,
            messages=anthropic_messages,
        )
        # Append assistant turn (bloques como vinieron)
        anthropic_messages.append({
            "role": "assistant",
            "content": [b.model_dump() for b in resp.content],
        })

        if resp.stop_reason != "tool_use":
            break

        # Ejecutar cada tool_use
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            text, maybe_report = await dispatch_tool(block.name, block.input or {})
            if maybe_report is not None:
                final_report = maybe_report
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": text,
            })

        anthropic_messages.append({"role": "user", "content": tool_results})

    # Extraer texto final del último assistant
    final_text = ""
    last = anthropic_messages[-1]
    if last["role"] == "assistant":
        for b in last["content"]:
            if isinstance(b, dict) and b.get("type") == "text":
                final_text += b.get("text", "")

    # Si compute_location_score se llamó, pedimos a Claude un resumen HTML también
    if final_report is not None and not final_report.get("resumen"):
        final_report["resumen"] = _derive_resumen_html(final_report, final_text)

    # Convertir historial de vuelta a formato simple para Dev B (strings)
    simple_messages = []
    for m in anthropic_messages:
        if isinstance(m["content"], str):
            simple_messages.append({"role": m["role"], "content": m["content"]})
        else:
            # Si es lista de bloques (assistant con text/tool_use, user con tool_result):
            # para el chat visible solo nos interesan los "text" del assistant
            text = ""
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "text":
                    text += b.get("text", "")
            if text or m["role"] == "user":
                simple_messages.append({"role": m["role"], "content": text})

    # Convertir markdown a HTML para que Vue v-html lo renderice bonito
    content_html = markdown_to_html(final_text) if final_text else "<p>Listo.</p>"

    return {
        "messages": simple_messages,
        "content": content_html,
        "reportData": final_report,
        "error": None,
    }


def _derive_resumen_html(report: dict, text: str) -> str:
    """Resumen HTML minimal a partir del reportData + texto de Claude."""
    g = report["scores"]["global"]
    et = report["scores"]["etiqueta_global"]
    dims = report["scores"]["dimensiones"]
    lines = [
        f"<h3>Resumen Ejecutivo: {report['direccion'].split(',')[0]}</h3>",
        f"<p><strong>Score global: {g}/10 ({et})</strong></p>",
        "<ul>",
    ]
    for d in sorted(dims, key=lambda x: -x["score"])[:4]:
        lines.append(
            f"<li><strong>{d['nombre']}:</strong> {d['score']}/10 — "
            f"<em>{d['fuente']}</em>: {d['dato_bruto']}</li>"
        )
    lines.append("</ul>")
    return "".join(lines)
