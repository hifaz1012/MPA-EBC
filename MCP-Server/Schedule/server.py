#!/usr/bin/env python3
"""
MCP server for MPA Schedule APIs.

Wraps 8 vessel schedule endpoints from MPA Oceans-X as MCP tools.
Each tool forwards the apikey header token to the upstream API.
"""

import os
from datetime import datetime
from typing import Any

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SERVER_INSTRUCTIONS = (
    "MPA Schedule MCP server exposing vessel schedule lookups for arrivals, "
    "departures, and due-to-arrive/depart queries. Every tool requires an "
    "`apikey` argument, which is forwarded to the upstream MPA Oceans-X API "
    "as the HTTP header `apikey`. Use YYYY-MM-DD dates and positive integer "
    "hours for hour-based queries."
)

# Initialize MCP server
mcp = FastMCP("mpa-schedule-mcp", instructions=SERVER_INSTRUCTIONS)

# Upstream API base URLs
BASE_URLS = {
    "arrivals": os.getenv("BASE_URL_ARRIVALS", "https://oceans-x.mpa.gov.sg/api/v1/vessel/arrivals/1.0.0"),
    "due_to_arrive": os.getenv("BASE_URL_DUE_TO_ARRIVE", "https://oceans-x.mpa.gov.sg/api/v1/vessel/duetoarrive/1.0.0"),
    "departures": os.getenv("BASE_URL_DEPARTURES", "https://oceans-x.mpa.gov.sg/api/v1/vessel/departure/1.0.0"),
    "due_to_depart": os.getenv("BASE_URL_DUE_TO_DEPART", "https://oceans-x.mpa.gov.sg/api/v1/vessel/duetodepart/1.0.0"),
}

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
MCP_HTTP_PATH = os.getenv("MCP_HTTP_PATH", "/mcp")
DEFAULT_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_check(_request: Request) -> Response:
    """Health endpoint for container platforms such as Azure Container Apps."""
    return JSONResponse({"status": "ok", "server": "mpa-schedule-mcp"})


def validate_date(date_str: str) -> None:
    """Validate date format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("date must be in YYYY-MM-DD format")


def validate_hours(hours: int) -> None:
    """Validate hours is a positive integer."""
    if not isinstance(hours, int) or hours <= 0:
        raise ValueError("hours must be a positive integer")


def build_headers(apikey: str) -> dict:
    """Build headers with apikey and Accept."""
    return {
        "apikey": apikey,
        "Accept": "application/json",
    }


def fetch_json(
    base_url: str,
    path: str,
    apikey: str,
    source: str,
) -> dict:
    """
    Fetch JSON from upstream API.
    
    Args:
        base_url: Base URL of the upstream API
        path: Path to append to base URL
        apikey: API key to forward as header
        source: Logical API name for response
        
    Returns:
        Structured JSON response with source, endpoint, count, and data
        
    Raises:
        RuntimeError: If upstream returns non-2xx status
    """
    endpoint = f"{base_url}{path}"
    headers = build_headers(apikey)
    
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(endpoint, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        error_body = ""
        try:
            error_body = e.response.text[:200]
        except Exception:
            pass
        raise RuntimeError(
            f"Upstream API error: {e.response.status_code}. Body: {error_body}"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to fetch from {endpoint}: {str(e)}")
    
    # Return structured response
    count = len(data) if isinstance(data, list) else None
    return {
        "source": source,
        "endpoint": endpoint,
        "count": count,
        "data": data,
    }


# ============================================================================
# Vessel Arrivals Tools
# ============================================================================

@mcp.tool()
def get_vessel_arrivals_by_date(date: str, apikey: str) -> dict:
    """
    Get vessel arrivals by date.
    
    Provides vessel arrival information for a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and arrival data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["arrivals"],
        f"/date/{date}",
        apikey,
        "Vessel Arrivals"
    )


@mcp.tool()
def get_vessel_arrivals_past_hours(date: str, hours: int, apikey: str) -> dict:
    """
    Get vessel arrivals for past N hours.
    
    Returns vessel arrivals for a given date and lookback hours in YYYY-MM-DD format.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of past hours to include (positive integer)
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and arrival data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["arrivals"],
        f"/date/{date}/hours/{hours}",
        apikey,
        "Vessel Arrivals (Past Hours)"
    )


# ============================================================================
# Vessels Due to Arrive Tools
# ============================================================================

@mcp.tool()
def get_vessels_due_to_arrive_by_date(date: str, apikey: str) -> dict:
    """
    Get vessels due to arrive by date.
    
    Provides vessel information for vessels due to arrive on a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["due_to_arrive"],
        f"/date/{date}",
        apikey,
        "Vessels Due to Arrive"
    )


@mcp.tool()
def get_vessels_due_to_arrive_next_hours(date: str, hours: int, apikey: str) -> dict:
    """
    Get vessels due to arrive for next N hours.
    
    Returns vessels due to arrive within a specified number of hours from a given date in YYYY-MM-DD format.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of hours ahead to include (positive integer)
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["due_to_arrive"],
        f"/date/{date}/hours/{hours}",
        apikey,
        "Vessels Due to Arrive (Next Hours)"
    )


# ============================================================================
# Vessel Departures Tools
# ============================================================================

@mcp.tool()
def get_vessel_departures_by_date(date: str, apikey: str) -> dict:
    """
    Get vessel departures by date.
    
    Provides vessel departure information for a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and departure data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["departures"],
        f"/date/{date}",
        apikey,
        "Vessel Departures"
    )


@mcp.tool()
def get_vessel_departures_past_hours(date: str, hours: int, apikey: str) -> dict:
    """
    Get vessel departures for past N hours.
    
    Returns vessel departures for a given date and lookback hours in YYYY-MM-DD format.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of past hours to include (positive integer)
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and departure data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["departures"],
        f"/date/{date}/hours/{hours}",
        apikey,
        "Vessel Departures (Past Hours)"
    )


# ============================================================================
# Vessels Due to Depart Tools
# ============================================================================

@mcp.tool()
def get_vessels_due_to_depart_by_date(date: str, apikey: str) -> dict:
    """
    Get vessels due to depart by date.
    
    Provides vessel information for vessels due to depart on a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["due_to_depart"],
        f"/date/{date}",
        apikey,
        "Vessels Due to Depart"
    )


@mcp.tool()
def get_vessels_due_to_depart_next_hours(date: str, hours: int, apikey: str) -> dict:
    """
    Get vessels due to depart for next N hours.
    
    Returns vessels due to depart within a specified number of hours from a given date in YYYY-MM-DD format.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of hours ahead to include (positive integer)
        apikey: API key for authentication (forwarded as HTTP header)
        
    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["due_to_depart"],
        f"/date/{date}/hours/{hours}",
        apikey,
        "Vessels Due to Depart (Next Hours)"
    )


def main() -> None:
    """Run the MCP server using stdio by default or HTTP for container hosting."""
    if DEFAULT_TRANSPORT in {"http", "streamable-http", "sse"}:
        mcp.run(
            transport=DEFAULT_TRANSPORT,
            host=HOST,
            port=PORT,
            path=MCP_HTTP_PATH,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
