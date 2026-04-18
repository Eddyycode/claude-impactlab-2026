"""
Cliente MCP stdio hacia `cdmx-mcp` (submódulo en `mcp cesar/`).

Mantiene una sesión persistente durante el lifespan de FastAPI.
Se arranca en startup, se cierra en shutdown.

Uso:
    mcp = CdmxMcpClient()
    await mcp.connect()
    tools = await mcp.list_tools()
    result = await mcp.call_tool("crime_hotspots", {"year": 2025, "top_n": 5})
    await mcp.close()
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Ruta absoluta al submódulo para evitar problemas de CWD
_REPO_ROOT = Path(__file__).resolve().parent.parent
_MCP_DIR = _REPO_ROOT / "mcp cesar"

_PARAMS = StdioServerParameters(
    command="uv",
    args=["--directory", str(_MCP_DIR), "run", "cdmx-mcp"],
    env=None,
)


class CdmxMcpClient:
    def __init__(self) -> None:
        self._stdio_ctx = None
        self._session_ctx = None
        self.session: Optional[ClientSession] = None
        self._tools_cache: Optional[list[dict]] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Arranca cdmx-mcp como subproceso stdio e inicializa la sesión MCP."""
        self._stdio_ctx = stdio_client(_PARAMS)
        read, write = await self._stdio_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self.session = await self._session_ctx.__aenter__()
        await self.session.initialize()

    async def close(self) -> None:
        try:
            if self._session_ctx:
                await self._session_ctx.__aexit__(None, None, None)
        except Exception as e:
            print(f"[mcp_client] close session error: {e}")
        try:
            if self._stdio_ctx:
                await self._stdio_ctx.__aexit__(None, None, None)
        except Exception as e:
            print(f"[mcp_client] close stdio error: {e}")

    async def list_tools(self) -> list[dict]:
        """Lista las tools del MCP en formato Anthropic tool schema."""
        if self._tools_cache is not None:
            return self._tools_cache
        resp = await self.session.list_tools()
        self._tools_cache = [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in resp.tools
        ]
        return self._tools_cache

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Llama una tool por nombre. Devuelve texto concatenado del result."""
        async with self._lock:   # un call a la vez — stdio es serial
            result = await self.session.call_tool(name, arguments or {})
        texts: list[str] = []
        for block in result.content:
            # block.type == "text" | "image" | ...
            if getattr(block, "type", "") == "text":
                texts.append(block.text)
        return "\n".join(texts) if texts else "(sin resultado)"
