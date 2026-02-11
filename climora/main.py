"""Minimal MCP server to fetch raw Climora measurements via processor endpoints.

Overview
This MCP server exposes three tools that proxy requests to the local processor API.
Each tool wraps the raw processor response with metadata (source, base_url, bounds,
counts, and normalized timestamps) so clients can understand what was queried, how
it was constrained, and where the data came from. This keeps the MCP contract stable
even if the processor payload evolves, and makes debugging and auditing easier.

How it works
- FastMCP registers Python functions as tools via the @mcp.tool() decorator.
- Each tool calls _fetch_data(), which performs a GET request to the processor.
- Responses are validated to ensure the expected shape (dict for latest, list for history).
- The tool returns a dict that includes the original data under a clear key
  ("measurement"/"measurements") plus metadata like "count" and "limit".

Why the return shape is wrapped
- Consistency: all tools return a dict even if the raw data is a list.
- Traceability: "source" and "base_url" document the upstream endpoint.
- Safety: bounds like "limit" are echoed back so callers know what was enforced.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

mcp = FastMCP("climora-influx-raw")

# Processor service base URL (local dev default).
PROCESSOR_BASE_URL = "http://localhost:8004"


class LatestMeasurementResponse(BaseModel):
    source: str
    base_url: str
    measurement: dict[str, Any]


class MeasurementHistoryResponse(BaseModel):
    source: str
    base_url: str
    limit: int
    count: int
    measurements: list[dict[str, Any]]


class MeasurementHistoryRangeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: str
    base_url: str
    from_: str = Field(alias="from")
    to: str
    limit: int
    count: int
    measurements: list[dict[str, Any]]


def _to_utc_iso(timestamp: str) -> str:
    """Normalize incoming timestamp to UTC ISO8601 with Z."""
    # Accept both "Z" and "+00:00" for UTC and strip accidental whitespace.
    value = datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _fetch_data(path: str, params: dict[str, Any] | None = None) -> Any:
    """Execute GET request against processor API and parse JSON."""
    query = urlencode(params or {})
    url = f"{PROCESSOR_BASE_URL}{path}?{query}" if query else f"{PROCESSOR_BASE_URL}{path}"
    request = Request(url=url, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Processor request failed ({exc.code}): {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Processor unreachable at {PROCESSOR_BASE_URL}: {exc}") from exc


@mcp.tool()
def get_latest_measurement() -> dict[str, Any]:
    """Return latest measurement from processor endpoint."""
    data = _fetch_data("/measurements/latest-measurement")
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response format from latest-measurement endpoint.")
    return LatestMeasurementResponse(
        source="processor:/measurements/latest-measurement",
        base_url=PROCESSOR_BASE_URL,
        measurement=data,
    ).model_dump()


@mcp.tool()
def get_measurement_history(limit: int = 50) -> dict[str, Any]:
    """Return raw measurement history from processor endpoint."""
    bounded_limit = max(1, min(limit, 500))
    data = _fetch_data("/measurements/history", {"limit": bounded_limit})
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from history endpoint.")
    return MeasurementHistoryResponse(
        source="processor:/measurements/history",
        base_url=PROCESSOR_BASE_URL,
        limit=bounded_limit,
        count=len(data),
        measurements=data,
    ).model_dump()


@mcp.tool()
def get_measurement_history_range(from_timestamp: str, to_timestamp: str, limit: int = 500) -> dict[str, Any]:
    """Return raw measurement history for a given time window."""
    bounded_limit = max(1, min(limit, 5000))
    start = _to_utc_iso(from_timestamp)
    end = _to_utc_iso(to_timestamp)
    data = _fetch_data(
        "/measurements/history/range",
        {"from": start, "to": end, "limit": bounded_limit},
    )
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from history/range endpoint.")
    return MeasurementHistoryRangeResponse(
        source="processor:/measurements/history/range",
        base_url=PROCESSOR_BASE_URL,
        from_=start,
        to=end,
        limit=bounded_limit,
        count=len(data),
        measurements=data,
    ).model_dump(by_alias=True)


if __name__ == "__main__":
    mcp.run()
