"""
Gateway FastAPI — MVP #1: eco-mock para probar integración Vue ↔ backend.

Por ahora devuelve un fixture hardcoded (Narvarte Poniente) para cualquier
pregunta. El próximo paso es reemplazar `mock_report()` con llamadas reales
a Claude API + cdmx-mcp.

Correr:
    cd gateway
    python -m venv .venv
    .venv\\Scripts\\activate   (Windows)  o  source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="ColonIA gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str
    content: str
    reportData: dict | None = None


class ChatRequest(BaseModel):
    messages: list[Message]
    preferences: dict | None = None


# --- fixture: Narvarte Poniente (mismo shape que el mock de Dev B) ---

FIXTURE_REPORT = {
    "direccion": "Narvarte Poniente, Ciudad de México",
    "lat": 19.3934,
    "lng": -99.155,
    "scores": {
        "global": 7.6,
        "etiqueta_global": "Bueno",
        "dimensiones": [
            {
                "id": "seguridad", "nombre": "Seguridad",
                "score": 7.8, "peso_aplicado": 20,
                "fuente": "FGJ CDMX", "dataset_id": "fgj",
                "consultado_en": "2026-04-18",
                "dato_bruto": "48 delitos / 1000 hab últimos 12m",
                "detalle": "Tendencia estable vs. trimestre previo",
            },
            {
                "id": "aire", "nombre": "Calidad del Aire",
                "score": 6.4, "peso_aplicado": 12,
                "fuente": "SIMAT", "dataset_id": "aire",
                "consultado_en": "2026-04-18",
                "dato_bruto": "PM2.5 alto recurrente",
                "detalle": "Estación más cercana: Benito Juárez",
            },
            {
                "id": "sismico", "nombre": "Riesgo sísmico",
                "score": 6.0, "peso_aplicado": 18,
                "fuente": "Atlas Riesgo CDMX", "dataset_id": "atlas-de-riesgo-sismico",
                "consultado_en": "2026-04-18",
                "dato_bruto": "Zona de transición (Zona II)",
                "detalle": "Aceleración sísmica media",
            },
            {
                "id": "inundacion", "nombre": "Riesgo de inundación",
                "score": 9.0, "peso_aplicado": 8,
                "fuente": "Atlas Riesgo CDMX", "dataset_id": "atlas-de-riesgo-inundaciones",
                "consultado_en": "2026-04-18",
                "dato_bruto": "Bajo riesgo de encharcamiento",
                "detalle": "Buen drenaje en la mayoría de calles",
            },
            {
                "id": "agua", "nombre": "Confiabilidad del Agua",
                "score": 7.2, "peso_aplicado": 14,
                "fuente": "SACMEX", "dataset_id": "reportes-de-agua",
                "consultado_en": "2026-04-18",
                "dato_bruto": "Reportes moderados/bajos",
                "detalle": "Suministro estable sin tandeo severo",
            },
            {
                "id": "transporte", "nombre": "Transporte Público",
                "score": 9.5, "peso_aplicado": 14,
                "fuente": "GTFS CDMX", "dataset_id": None,
                "consultado_en": "2026-04-18",
                "dato_bruto": "14 paradas RTP en 800 m",
                "detalle": "Múltiples opciones en radio de 800m",
            },
            {
                "id": "integridad_2017", "nombre": "Integridad 2017",
                "score": 8.0, "peso_aplicado": 8,
                "fuente": "Atlas Zona Cero 2017", "dataset_id": "atlas-de-riesgo-zona-cero-2017",
                "consultado_en": "2026-04-18",
                "dato_bruto": "2 inmuebles afectados en radio 300m",
                "detalle": "Severidad menor a demolición",
            },
            {
                "id": "servicios", "nombre": "Servicios Cercanos",
                "score": 7.5, "peso_aplicado": 4,
                "fuente": "DENUE INEGI", "dataset_id": None,
                "consultado_en": "2026-04-18",
                "dato_bruto": "Cobertura completa en 800 m",
                "detalle": "Todo a menos de 10 min caminando",
            },
        ],
        "faltantes": [
            {"id": "ecobici", "razon": "Fallo conexión GBFS (simulado)"},
        ],
    },
    "resumen": (
        "<h3>Resumen Ejecutivo: Narvarte Poniente</h3>"
        "<p>Evaluación general sólida (<strong>7.6/10</strong>). Zona céntrica con "
        "excelente acceso a transporte y oferta comercial. Tradeoffs: riesgo sísmico "
        "por zona de transición y episodios de mala calidad del aire.</p>"
        "<p><em>Generado por el gateway (mock) — "
        "próxima iteración: datos en vivo vía cdmx-mcp.</em></p>"
    ),
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mcp": "not_wired_yet", "supabase": "not_wired_yet"}


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    last_user = next(
        (m for m in reversed(req.messages) if m.role == "user"),
        None,
    )
    query = last_user.content if last_user else "(sin mensaje)"

    content_text = f"Recibí tu pregunta: «{query}». Aquí tienes la evaluación:"

    new_messages = [m.model_dump() for m in req.messages]
    new_messages.append({
        "role": "assistant",
        "content": content_text,
        "reportData": FIXTURE_REPORT,
    })

    return {
        "messages": new_messages,
        "content": content_text,
        "reportData": FIXTURE_REPORT,
        "error": None,
    }
