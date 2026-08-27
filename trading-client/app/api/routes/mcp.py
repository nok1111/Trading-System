"""MCP (Model Context Protocol) API routes.

Endpoints:
  GET    /api/mcp/config    — get MCP config JSON for AI clients (auth)
  POST   /api/mcp/session   — start MCP session, generate token (auth)
  DELETE /api/mcp/session   — close MCP session (auth)
  POST   /api/mcp/rpc       — JSON-RPC endpoint for MCP tool calls (auth)
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.config import get_settings
from app.mcp.server import AlvoraMCPServer
from app.services.auth import LocalUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mcp", tags=["mcp"])

_server = AlvoraMCPServer()


class RPCRequest(BaseModel):
    """JSON-RPC 2.0 request envelope."""
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | list[Any] | None = None


@router.get("/config")
def get_mcp_config(
    request: Request,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get MCP config JSON for Claude / ChatGPT / Cursor.

    Uses the user's JWT from the Authorization header as the MCP token.
    Returns a ready-to-paste config with the server URL and auth header.
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    settings = get_settings()

    # Determine base URL — use the request's host for convenience
    base_url = str(request.base_url).rstrip("/")

    config = AlvoraMCPServer.generate_mcp_config(token, base_url)
    return {
        "config": config,
        "config_json": _format_json(config),
        "base_url": base_url,
        "tools": [t["name"] for t in AlvoraMCPServer.TOOLS],
        "tool_count": len(AlvoraMCPServer.TOOLS),
    }


@router.post("/session")
def start_session(
    request: Request,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Start a new MCP session and generate a dedicated MCP token.

    The MCP token is separate from the JWT and has a 1-hour TTL.
    Use it in the Authorization header for /api/mcp/rpc calls.
    """
    token = AlvoraMCPServer.create_session(current_user.id, current_user.email)
    settings = get_settings()
    base_url = str(request.base_url).rstrip("/")
    return {
        "token": token,
        "expires_in": 3600,
        "rpc_url": f"{base_url}/api/mcp/rpc",
        "config_url": f"{base_url}/api/mcp/config",
    }


@router.delete("/session")
def close_session(
    request: Request,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Close an MCP session by token."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    # Try as MCP session token first
    closed = AlvoraMCPServer.close_session(token)
    return {"closed": closed}


@router.post("/rpc")
async def rpc_endpoint(
    request: Request,
) -> dict:
    """JSON-RPC endpoint for MCP tool calls.

    Accepts a JSON-RPC 2.0 request and dispatches to the appropriate tool.
    Authentication is via the Bearer token (JWT or MCP session token).
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Support both single request and batch
    if isinstance(body, list):
        # Batch request
        results = []
        for req in body:
            results.append(_handle_single_rpc(req, token))
        return {"batch": results}

    return _handle_single_rpc(body, token)


def _handle_single_rpc(body: dict[str, Any], token: str) -> dict[str, Any]:
    """Handle a single JSON-RPC request."""
    method = body.get("method", "")
    params = body.get("params")
    req_id = body.get("id")

    if isinstance(params, list):
        # Convert positional params to dict (best effort)
        params = {"args": params}

    result = _server.handle_request(method, params, token)

    response: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if "error" in result:
        response["error"] = result["error"]
    else:
        response["result"] = result.get("result")
    return response


def _format_json(obj: Any, indent: int = 2) -> str:
    """Format a dict as pretty JSON string."""
    import json

    return json.dumps(obj, indent=indent, ensure_ascii=False)
