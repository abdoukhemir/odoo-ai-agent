#!/usr/bin/env python3
"""
MCP Bridge Server for Odoo
===========================
Bridges VS Code / Claude Desktop / Cursor to Odoo MCP Server REST API.

Usage:
    python3 mcp_bridge.py

Environment variables:
    ODOO_URL      - Odoo server URL (default: http://localhost:8069)
    ODOO_API_KEY  - Odoo API key (Bearer token)
    ODOO_LOGIN    - Odoo login (if not using API key)
    ODOO_PASSWORD - Odoo password (if not using API key)
    ODOO_DB       - Odoo database name (required for multi-database production servers)
"""

import base64
import json
import os
import httpx
from mcp.server.fastmcp import FastMCP

# ── Configuration ──────────────────────────────────────────────────────
ODOO_URL = os.environ.get("ODOO_URL", "http://localhost:8069").rstrip("/")
ODOO_API_KEY = os.environ.get("ODOO_API_KEY", "")
ODOO_LOGIN = os.environ.get("ODOO_LOGIN", "")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "")
ODOO_DB = os.environ.get("ODOO_DB", "")

# Build auth header + database header
AUTH_HEADERS = {}
if ODOO_API_KEY:
    AUTH_HEADERS["Authorization"] = f"Bearer {ODOO_API_KEY}"
elif ODOO_LOGIN and ODOO_PASSWORD:
    b64 = base64.b64encode(f"{ODOO_LOGIN}:{ODOO_PASSWORD}".encode()).decode()
    AUTH_HEADERS["Authorization"] = f"Basic {b64}"

# Send database name in header for multi-db production servers
# Odoo 19 natively reads 'X-Odoo-Database' header for DB selection
if ODOO_DB:
    AUTH_HEADERS["X-Odoo-Database"] = ODOO_DB

# ── HTTP Client ────────────────────────────────────────────────────────
client = httpx.Client(base_url=ODOO_URL, headers=AUTH_HEADERS, timeout=30.0)

# ── MCP Server ─────────────────────────────────────────────────────────
mcp = FastMCP(
    "Odoo MCP Server",
    # description="Connect to Odoo ERP via MCP - search, read, create, update records",
)


def _api_get(path: str) -> dict:
    """GET request to Odoo MCP API."""
    resp = client.get(f"/mcp/api/v1{path}")
    resp.raise_for_status()
    return resp.json()


def _api_post(path: str, data: dict) -> dict:
    """POST request to Odoo MCP API."""
    resp = client.post(f"/mcp/api/v1{path}", json=data)
    resp.raise_for_status()
    return resp.json()


# ── Tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def odoo_health() -> str:
    """Check if Odoo MCP Server is running and enabled."""
    result = _api_get("/health")
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_system_info() -> str:
    """Get Odoo system information: version, database, exposed models count."""
    result = _api_get("/system/info")
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_list_models() -> str:
    """List all models exposed via MCP with their CRUD permissions."""
    result = _api_get("/models")
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_model_fields(model: str) -> str:
    """Get field metadata for an Odoo model.

    Args:
        model: Model technical name, e.g. 'res.partner', 'sale.order'
    """
    model_path = model.replace(".", "-")
    result = _api_get(f"/models/{model_path}/fields")
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_search(
    model: str,
    domain: str = "[]",
    fields: str = "",
    limit: int = 20,
    offset: int = 0,
    order: str = "",
) -> str:
    """Search Odoo records with domain filter.

    Args:
        model: Model technical name, e.g. 'res.partner'
        domain: Odoo domain filter as JSON string, e.g. '[["is_company","=",true]]'
        fields: Comma-separated field names, e.g. 'name,email,phone'. Empty = smart defaults.
        limit: Max records to return (default 20)
        offset: Pagination offset (default 0)
        order: Sort order, e.g. 'name asc' or 'create_date desc'
    """
    model_path = model.replace(".", "-")
    body = {
        "domain": json.loads(domain) if domain else [],
        "limit": limit,
        "offset": offset,
    }
    if fields:
        body["fields"] = [f.strip() for f in fields.split(",")]
    if order:
        body["order"] = order

    result = _api_post(f"/models/{model_path}/search", body)
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_read(model: str, ids: str, fields: str = "") -> str:
    """Read specific Odoo records by their IDs.

    Args:
        model: Model technical name, e.g. 'res.partner'
        ids: Comma-separated record IDs, e.g. '1,2,3'
        fields: Comma-separated field names. Empty = smart defaults.
    """
    model_path = model.replace(".", "-")
    body = {
        "ids": [int(i.strip()) for i in ids.split(",")],
    }
    if fields:
        body["fields"] = [f.strip() for f in fields.split(",")]

    result = _api_post(f"/models/{model_path}/read", body)
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_browse(
    model: str,
    domain: str = "[]",
    fields: str = "",
    limit: int = 20,
    offset: int = 0,
    order: str = "",
    summary: bool = True,
) -> str:
    """Browse Odoo records with pagination info and optional summary.

    Args:
        model: Model technical name, e.g. 'res.partner'
        domain: Odoo domain filter as JSON string
        fields: Comma-separated field names. Empty = smart defaults.
        limit: Records per page (default 20)
        offset: Pagination offset (default 0)
        order: Sort order, e.g. 'name asc'
        summary: Include LLM-friendly summary (default True)
    """
    model_path = model.replace(".", "-")
    body = {
        "domain": json.loads(domain) if domain else [],
        "limit": limit,
        "offset": offset,
        "summary": summary,
    }
    if fields:
        body["fields"] = [f.strip() for f in fields.split(",")]
    if order:
        body["order"] = order

    result = _api_post(f"/models/{model_path}/browse", body)
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_count(model: str, domain: str = "[]") -> str:
    """Count Odoo records matching a domain filter.

    Args:
        model: Model technical name, e.g. 'res.partner'
        domain: Odoo domain filter as JSON string, e.g. '[["is_company","=",true]]'
    """
    model_path = model.replace(".", "-")
    body = {"domain": json.loads(domain) if domain else []}
    result = _api_post(f"/models/{model_path}/count", body)
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_create(model: str, values: str) -> str:
    """Create a new record in Odoo.

    Args:
        model: Model technical name, e.g. 'res.partner'
        values: JSON string of field values, e.g. '{"name": "John", "email": "john@test.com"}'
    """
    model_path = model.replace(".", "-")
    body = {"values": json.loads(values)}
    result = _api_post(f"/models/{model_path}/create", body)
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_write(model: str, ids: str, values: str) -> str:
    """Update existing Odoo records.

    Args:
        model: Model technical name, e.g. 'res.partner'
        ids: Comma-separated record IDs to update, e.g. '1,2,3'
        values: JSON string of field values to update, e.g. '{"name": "Updated Name"}'
    """
    model_path = model.replace(".", "-")
    body = {
        "ids": [int(i.strip()) for i in ids.split(",")],
        "values": json.loads(values),
    }
    result = _api_post(f"/models/{model_path}/write", body)
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_delete(model: str, ids: str) -> str:
    """Delete Odoo records by IDs.

    Args:
        model: Model technical name, e.g. 'res.partner'
        ids: Comma-separated record IDs to delete, e.g. '5,6,7'
    """
    model_path = model.replace(".", "-")
    body = {"ids": [int(i.strip()) for i in ids.split(",")]}
    result = _api_post(f"/models/{model_path}/unlink", body)
    return json.dumps(result, indent=2)


@mcp.tool()
def odoo_call_method(
    model: str, method: str, ids: str = "", args: str = "[]", kwargs: str = "{}"
) -> str:
    """Call a method on an Odoo model.

    Args:
        model: Model technical name, e.g. 'res.partner'
        method: Method name, e.g. 'name_search'
        ids: Optional comma-separated record IDs to call on, e.g. '1,2'
        args: JSON array of positional arguments, e.g. '["Admin"]'
        kwargs: JSON object of keyword arguments, e.g. '{"limit": 5}'
    """
    model_path = model.replace(".", "-")
    body = {
        "method": method,
        "args": json.loads(args) if args else [],
        "kwargs": json.loads(kwargs) if kwargs else {},
    }
    if ids:
        body["ids"] = [int(i.strip()) for i in ids.split(",")]

    result = _api_post(f"/models/{model_path}/call", body)
    return json.dumps(result, indent=2)


# ── Resources ──────────────────────────────────────────────────────────

@mcp.resource("odoo://health")
def resource_health() -> str:
    """Odoo MCP Server health status."""
    return json.dumps(_api_get("/health"), indent=2)


@mcp.resource("odoo://models")
def resource_models() -> str:
    """List of all exposed Odoo models."""
    return json.dumps(_api_get("/models"), indent=2)


# ── Run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
