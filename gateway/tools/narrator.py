"""
Narrador: Claude convierte las dimensiones numéricas en:
- `content`: texto del chat (1–2 párrafos en markdown)
- `resumen`: HTML del reporte ejecutivo

Sin tool use: Claude solo interpreta los datos que ya calculó el gateway.
El modelo recibe las dimensiones ya resueltas y no llama herramientas externas.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from anthropic import Anthropic

MODEL = "claude-sonnet-4-5"

_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key or not key.startswith("sk-ant-"):
            raise RuntimeError("ANTHROPIC_API_KEY no está configurado en .env")
        _client = Anthropic(api_key=key)
    return _client


SYSTEM_PROMPT = """\
Eres un agente experto en calidad de vida urbana en la Ciudad de México.
Recibes una colonia/dirección ya evaluada con scores 1–10 por dimensión,
basados en datos abiertos de gobierno (FGJ, SIMAT, Atlas de Riesgo CDMX,
SACMEX, GTFS, DENUE). Tu trabajo es **interpretar** esos números en español
claro, sin inventar datos que no estén en el input.

Convenciones:
- Score 1–3.9 = "Evitar"; 4–5.4 = "Preocupante"; 5.5–6.9 = "Aceptable";
  7–8.4 = "Bueno"; 8.5–10 = "Excelente".
- Menciona siempre la fuente gubernamental clave (FGJ, SIMAT, etc.) al
  hablar de una dimensión.
- Si hay dimensiones en `faltantes`, mencionalas honestamente al final.
- Nunca inventes un número que no esté en el input.

Formato de salida — **devuelve SOLO JSON válido**, sin texto antes ni después,
sin bloque de código ```:

{
  "content": "<1–2 párrafos en markdown, 60–120 palabras, tono claro y directo; empieza con una línea de veredicto>",
  "resumen": "<HTML empezando con <h3>Resumen Ejecutivo: {colonia}</h3>, seguido de 2–3 <p> con análisis; usa <strong> en los puntos clave; sin CSS inline>"
}
"""


def narrate(query: str, alcaldia: str, dimensiones: list, faltantes: list,
            global_score: float, etiqueta_global: str) -> dict:
    """Llama Claude para generar content + resumen. Devuelve {"content","resumen"}."""
    payload = {
        "query_del_usuario": query,
        "alcaldia": alcaldia,
        "score_global": global_score,
        "etiqueta_global": etiqueta_global,
        "dimensiones": dimensiones,
        "faltantes": faltantes,
    }
    user_msg = (
        "Datos de la evaluación (JSON):\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = "".join(block.text for block in resp.content if block.type == "text").strip()

    # Por si Claude envolvió en ```json ... ``` a pesar del prompt
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    try:
        data = json.loads(raw)
        return {
            "content": data.get("content", "").strip(),
            "resumen": data.get("resumen", "").strip(),
        }
    except json.JSONDecodeError as e:
        print(f"[narrator] JSON parse error: {e}\nRAW:\n{raw[:500]}")
        # Fallback amable
        return {
            "content": f"Analicé **{query}**: score global {global_score}/10 ({etiqueta_global}).",
            "resumen": f"<h3>Resumen: {query}</h3><p>Score global: <strong>{global_score}/10</strong>.</p>",
        }
