"""Standalone TRACE MCP server (Python MCP SDK / FastMCP).

Blueprint: MCP server MVP with Python MCP SDK; FastMCP preferred.
Runs as a separate stdio process for external agent clients while the
in-process EvidenceTools adapter remains the default for FastAPI agents.

Usage:
    python -m app.core.mcp.server
    # or with HTTP transport:
    TRACE_MCP_TRANSPORT=http python -m app.core.mcp.server
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.database import SessionLocal
from app.core.mcp.tools import EvidenceTools
from app.core.mcp.weather_tools import fetch_weather_at_location as fetch_weather_impl


mcp = FastMCP(
    "TRACE",
    instructions=(
        "TRACE investigation MCP server. Use fetch_weather_at_location with "
        "accident-site latitude/longitude to retrieve environmental conditions. "
        "When CASE_ID is set in the environment, evidence read tools are "
        "scoped to that investigation case."
    ),
)


def _case_id_from_env() -> uuid.UUID | None:
    raw = os.environ.get("TRACE_CASE_ID", "").strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _evidence_tools() -> EvidenceTools | dict[str, str]:
    case_id = _case_id_from_env()
    if case_id is None:
        return {
            "error": "Set TRACE_CASE_ID environment variable for evidence tools"
        }
    db = SessionLocal()
    return EvidenceTools(db, case_id)


@mcp.tool()
def fetch_weather_at_location(
    latitude: float,
    longitude: float,
    at_time: str | None = None,
) -> dict[str, Any]:
    """Fetch weather observations at accident-site coordinates.

    Args:
        latitude: Accident latitude in decimal degrees (-90 to 90).
        longitude: Accident longitude in decimal degrees (-180 to 180).
        at_time: Optional ISO8601 timestamp for historical lookup near incident time.
    """
    return fetch_weather_impl(
        None,
        case_id=None,
        latitude=latitude,
        longitude=longitude,
        at_time=at_time,
    )


@mcp.tool()
def query_evidence(
    source_type: str | None = None,
    q: str | None = None,
    evidence_id: str | None = None,
    is_valid: bool | None = True,
    limit: int = 25,
) -> dict[str, Any]:
    """Retrieve evidence records for the active TRACE case (TRACE_CASE_ID)."""
    tools = _evidence_tools()
    if isinstance(tools, dict):
        return tools
    try:
        return tools.query_evidence(
            source_type=source_type,
            q=q,
            evidence_id=evidence_id,
            is_valid=is_valid,
            limit=limit,
        )
    finally:
        tools.db.close()


@mcp.tool()
def get_domain_features() -> dict[str, Any]:
    """Return deterministic domain preprocessor scores for the active case."""
    tools = _evidence_tools()
    if isinstance(tools, dict):
        return tools
    try:
        return tools.get_domain_features()
    finally:
        tools.db.close()


@mcp.tool()
def get_evidence_gaps() -> dict[str, Any]:
    """List missing source types and domain inputs for the active case."""
    tools = _evidence_tools()
    if isinstance(tools, dict):
        return tools
    try:
        return tools.get_evidence_gaps()
    finally:
        tools.db.close()


def main() -> None:
    transport = os.environ.get("TRACE_MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        host = os.environ.get("TRACE_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("TRACE_MCP_PORT", "8765"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
