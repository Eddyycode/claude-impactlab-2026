"""
gateway/tools/tavily_search.py

Tool de búsqueda web con Tavily para enriquecer el contexto de cada consulta.
Úsalo para obtener información reciente sobre colonias, noticias, opiniones,
infraestructura y cualquier contexto que CKAN/MCP no cubra.
"""

from __future__ import annotations
import os
from tavily import TavilyClient

_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY no configurada en .env")
        _client = TavilyClient(api_key=api_key)
    return _client


async def search_neighborhood_context(query: str, location: str = "Ciudad de México") -> str:
    """
    Busca contexto web reciente sobre una colonia o dirección en CDMX.
    
    Combina la query del usuario + el nombre de la zona para buscar:
    - Noticias recientes sobre la colonia
    - Opiniones y reseñas de residentes
    - Información sobre servicios, seguridad, infraestructura
    - Proyectos urbanos o cambios recientes
    
    Devuelve un string con el contexto relevante para pasarle a Claude.
    """
    client = _get_client()
    
    # Construir una query específica para CDMX
    search_query = f"{query} {location} colonia"
    
    try:
        result = client.search(
            query=search_query,
            search_depth="advanced",        # más contexto
            include_answer=True,            # resumen directo de Tavily
            include_raw_content=False,
            max_results=5,
            include_domains=[
                "chilango.com",
                "eluniversal.com.mx",
                "milenio.com",
                "excelsior.com.mx",
                "expansion.mx",
                "infobae.com",
                "animalpolitico.com",
                "tiempo.com.mx",
            ],
        )
        
        # Armar contexto legible para Claude
        parts = []
        
        if result.get("answer"):
            parts.append(f"Resumen web: {result['answer']}")
        
        for r in result.get("results", [])[:4]:
            title = r.get("title", "")
            content = r.get("content", "")[:400]  # limitar tokens
            url = r.get("url", "")
            if content:
                parts.append(f"• {title}: {content} [{url}]")
        
        return "\n".join(parts) if parts else "Sin resultados web adicionales."
        
    except Exception as e:
        return f"Búsqueda web no disponible: {str(e)}"


# Definición de la tool para Claude API (format Anthropic)
TAVILY_TOOL_DEFINITION = {
    "name": "search_web_context",
    "description": (
        "Busca en internet contexto reciente y específico sobre una colonia, "
        "dirección o zona de CDMX. Úsalo para complementar los datos de gobierno "
        "con noticias recientes, opiniones de residentes, cambios de infraestructura, "
        "proyectos urbanos en curso, o cualquier información que los datasets "
        "oficiales no cubren. Úsalo SIEMPRE antes de generate_report para "
        "enriquecer el resumen ejecutivo con contexto cualitativo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Qué buscar, ej: 'seguridad Narvarte Poniente 2025' o 'transporte Roma Norte'"
            }
        },
        "required": ["query"]
    }
}
