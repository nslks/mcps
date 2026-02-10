"""Minimal MCP server to fetch raw Climora measurements via processor endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("climora-influx-raw")

PROCESSOR_BASE_URL = "http://localhost:8004"


def _to_utc_iso(timestamp: str) -> str:
    """Normalize incoming timestamp to UTC ISO8601 with Z."""
    value = datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _get_json(path: str, params: dict[str, Any] | None = None) -> Any:
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
    data = _get_json("/measurements/latest-measurement")
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response format from latest-measurement endpoint.")
    return {
        "source": "processor:/measurements/latest-measurement",
        "base_url": PROCESSOR_BASE_URL,
        "measurement": data,
    }


@mcp.tool()
def get_measurement_history(limit: int = 50) -> dict[str, Any]:
    """Return raw measurement history from processor endpoint."""
    bounded_limit = max(1, min(limit, 500))
    data = _get_json("/measurements/history", {"limit": bounded_limit})
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from history endpoint.")
    return {
        "source": "processor:/measurements/history",
        "base_url": PROCESSOR_BASE_URL,
        "limit": bounded_limit,
        "count": len(data),
        "measurements": data,
    }


@mcp.tool()
def get_measurement_history_range(from_timestamp: str, to_timestamp: str, limit: int = 500) -> dict[str, Any]:
    """Return raw measurement history for a given time window."""
    bounded_limit = max(1, min(limit, 5000))
    start = _to_utc_iso(from_timestamp)
    end = _to_utc_iso(to_timestamp)
    data = _get_json(
        "/measurements/history/range",
        {"from": start, "to": end, "limit": bounded_limit},
    )
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from history/range endpoint.")
    return {
        "source": "processor:/measurements/history/range",
        "base_url": PROCESSOR_BASE_URL,
        "from": start,
        "to": end,
        "limit": bounded_limit,
        "count": len(data),
        "measurements": data,
    }


if __name__ == "__main__":
    mcp.run()
