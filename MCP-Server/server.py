#!/usr/bin/env python3
"""
Root MCP server for MPA Oceans-X APIs.

Wraps vessel schedule, port, and vessel info endpoints from MPA Oceans-X as MCP tools.
The server lives at the MCP-Server root so API groups can be added into one shared
MCP server over time. Each tool forwards the apikey header token to the upstream API.
"""

import os
import re
from datetime import datetime
from typing import Any, Optional

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SERVER_INSTRUCTIONS = (
    "Root MPA Oceans-X MCP server exposing vessel schedule, port, and vessel info lookups "
    "over streamable HTTP. Provides Schedule (arrivals, departures, due-to-arrive/depart), "
    "Port (vessel movements and positions), and Vessel Info (vessel particulars and SRS "
    "certificate) tools. Every tool requires an `apikey` argument, which is forwarded to "
    "the upstream MPA Oceans-X API as the HTTP header `apikey`. Use YYYY-MM-DD dates and "
    "positive integer hours for hour-based queries."
)

# Initialize MCP server
mcp = FastMCP("mpa-ocx-mcp", instructions=SERVER_INSTRUCTIONS)

# Upstream API base URLs
BASE_URLS = {
    # Schedule
    "arrivals": os.getenv("BASE_URL_ARRIVALS", "https://oceans-x.mpa.gov.sg/api/v1/vessel/arrivals/1.0.0"),
    "due_to_arrive": os.getenv("BASE_URL_DUE_TO_ARRIVE", "https://oceans-x.mpa.gov.sg/api/v1/vessel/duetoarrive/1.0.0"),
    "departures": os.getenv("BASE_URL_DEPARTURES", "https://oceans-x.mpa.gov.sg/api/v1/vessel/departure/1.0.0"),
    "due_to_depart": os.getenv("BASE_URL_DUE_TO_DEPART", "https://oceans-x.mpa.gov.sg/api/v1/vessel/duetodepart/1.0.0"),
    # Port
    "movements": os.getenv("BASE_URL_MOVEMENTS", "https://oceans-x.mpa.gov.sg/api/v1/vessel/movements/1.0.0"),
    "positions": os.getenv("BASE_URL_POSITIONS", "https://oceans-x.mpa.gov.sg/api/v1/vessel/positions/1.0.0"),
    # Vessel Info
    "particulars": os.getenv("BASE_URL_PARTICULARS", "https://oceans-x.mpa.gov.sg/api/v1/vessel/particulars/1.0.0"),
    "srscor": os.getenv("BASE_URL_SRSCOR", "https://oceans-x.mpa.gov.sg/api/v1/vessel/srscor/1.0.0"),
}

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
MCP_HTTP_PATH = os.getenv("MCP_HTTP_PATH", "/mcp")
DEFAULT_TRANSPORT = "streamable-http"

# Precompiled regex patterns for validation
PATTERN_ALNUM = re.compile(r"^[a-zA-Z0-9]+$")
PATTERN_TEXT_WITH_SPACES = re.compile(r"^[0-9a-zA-Z-_. ']+$")



@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_check(_request: Request) -> Response:
    """Health endpoint for container platforms such as Azure Container Apps."""
    return JSONResponse({"status": "ok", "server": "mpa-ocx-mcp"})


def validate_apikey(apikey: str) -> None:
    """Validate that apikey is a non-empty string."""
    if not apikey or not isinstance(apikey, str) or len(apikey.strip()) == 0:
        raise ValueError("apikey must be a non-empty string")


def validate_string(
    value: str,
    field_name: str,
    pattern: re.Pattern,
    min_length: int,
    max_length: int,
) -> None:
    """
    Validate a string parameter against length and pattern constraints.

    Args:
        value: The string to validate
        field_name: Name of the field (for error messages)
        pattern: Compiled regex pattern to match
        min_length: Minimum string length
        max_length: Maximum string length

    Raises:
        ValueError: If validation fails
    """
    if value is None:
        raise ValueError(f"{field_name} cannot be None")

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    if len(value) < min_length or len(value) > max_length:
        raise ValueError(
            f"{field_name} must be between {min_length} and {max_length} characters, got {len(value)}"
        )

    if not pattern.match(value):
        raise ValueError(f"{field_name} format is invalid")


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
    query_params: Optional[dict] = None,
) -> dict:
    """
    Fetch JSON from upstream API.

    Args:
        base_url: Base URL of the upstream API
        path: Path to append to base URL
        apikey: API key to forward as header
        source: Logical API name for response
        query_params: Optional dict of query parameters

    Returns:
        Structured JSON response with source, endpoint, count, and data

    Raises:
        ValueError: If apikey or parameters are invalid
        RuntimeError: If upstream returns non-2xx status or connection fails
    """
    validate_apikey(apikey)

    endpoint = f"{base_url}{path}"
    headers = build_headers(apikey)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(endpoint, headers=headers, params=query_params)
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




# ============================================================================
# Vessel Positions Tools
# ============================================================================

@mcp.tool()
def get_vessel_positions_snapshot(apikey: str) -> dict:
    """
    Get all vessel positions (snapshot).

    Returns a snapshot of current positions for all vessels in the port area.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.

    Args:
        apikey: API key for authentication (forwarded as HTTP header)

    Returns:
        JSON object containing source, endpoint, count, and position data
    """
    return fetch_json(
        BASE_URLS["positions"],
        "/snapshot",
        apikey,
        "Vessel Positions (Snapshot)"
    )


@mcp.tool()
def get_vessel_positions_by_imo(imonumber: str, apikey: str) -> dict:
    """
    Get vessel positions by IMO number.

    Retrieves current position information for a specific vessel identified by IMO number.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.

    Args:
        imonumber: IMO number of the vessel (1-10 characters, alphanumeric)
        apikey: API key for authentication (forwarded as HTTP header)

    Returns:
        JSON object containing source, endpoint, count, and position data
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["positions"],
        f"/imonumber/{imonumber}",
        apikey,
        "Vessel Positions by IMO"
    )


@mcp.tool()
def get_vessel_movements_by_imo(imonumber: str, apikey: str) -> dict:
    """
    Get vessel movements by IMO number.

    Retrieves movement history for a specific vessel identified by IMO number.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.

    Args:
        imonumber: IMO number of the vessel (1-10 characters, alphanumeric)
        apikey: API key for authentication (forwarded as HTTP header)

    Returns:
        JSON object containing source, endpoint, count, and movement data
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["movements"],
        f"/imonumber/{imonumber}",
        apikey,
        "Vessel Movements by IMO"
    )


# ============================================================================
# Vessel Particulars Tools
# ============================================================================

@mcp.tool()
def get_vessel_particulars_by_name_pattern(charset: str, apikey: str) -> dict:
    """
    Get vessel particulars by vessel name pattern.

    Searches for vessels by a name pattern containing letters, digits, hyphens, underscores,
    periods, spaces, and apostrophes. The pattern is case-sensitive and must be 3-8 characters long.

    Examples of valid patterns:
    - "MAERSK" (6 chars)
    - "MSC" (3 chars, minimum)
    - "CMA-CGM" (7 chars including hyphen)
    - "ONE.." (5 chars with periods)

    Args:
        charset: Name pattern (3-8 chars, alphanumeric + hyphens, underscores, periods, spaces, apostrophes)
        apikey: API key for authentication (forwarded as HTTP header)

    Returns:
        JSON object containing source, endpoint, count, and vessel particulars
    """
    validate_string(charset, "charset", PATTERN_TEXT_WITH_SPACES, 3, 8)
    return fetch_json(
        BASE_URLS["particulars"],
        f"/name/{charset}",
        apikey,
        "Vessel Particulars by Name Pattern"
    )


@mcp.tool()
def get_vessel_particulars_by_imo(imonumber: str, apikey: str) -> dict:
    """
    Get vessel particulars by IMO number.

    Retrieves detailed information about a specific vessel identified by IMO number.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.

    Args:
        imonumber: IMO number of the vessel (1-10 characters, alphanumeric)
        apikey: API key for authentication (forwarded as HTTP header)

    Returns:
        JSON object containing source, endpoint, count, and vessel particulars
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["particulars"],
        f"/imonumber/{imonumber}",
        apikey,
        "Vessel Particulars by IMO"
    )


# ============================================================================
# SRS Certificate Tools
# ============================================================================

@mcp.tool()
def get_srs_certificate_by_certificate_number(certificatenumber: str, apikey: str) -> dict:
    """
    Get SRS certificate by certificate number.

    Retrieves the SRS (Singapore Registry of Ships) Certificate of Registry by its certificate number.
    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.

    Args:
        certificatenumber: Certificate number (1-15 characters, alphanumeric + hyphens, underscores, periods, spaces, apostrophes)
        apikey: API key for authentication (forwarded as HTTP header)

    Returns:
        JSON object containing source, endpoint, count, and SRS certificate data
    """
    validate_string(certificatenumber, "certificatenumber", PATTERN_TEXT_WITH_SPACES, 1, 15)
    return fetch_json(
        BASE_URLS["srscor"],
        f"/certificatenumber/{certificatenumber}",
        apikey,
        "SRS Certificate by Certificate Number"
    )


@mcp.tool()
def get_srs_certificate_by_vessel_details(
    officialnumber: str,
    vesselname: str,
    registryportnumber: str,
    apikey: str,
    imonumber: Optional[str] = None,
    callsign: Optional[str] = None,
) -> dict:
    """
    Get SRS certificate by vessel details.

    Retrieves the SRS (Singapore Registry of Ships) Certificate of Registry using vessel details.
    Three parameters are required: official number, vessel name, and registry port number.
    IMO number and call sign are optional for narrowing results.

    The apikey parameter is forwarded to the MPA API as the 'apikey' HTTP header.

    Args:
        officialnumber: Official vessel number (1-11 characters, alphanumeric) [required]
        vesselname: Vessel name (1-35 characters, alphanumeric + hyphens, underscores, periods, spaces, apostrophes) [required]
        registryportnumber: Registry port number (1-8 characters, alphanumeric) [required]
        imonumber: IMO number (1-10 characters, alphanumeric) [optional]
        callsign: Call sign (1-8 characters, alphanumeric) [optional]
        apikey: API key for authentication (forwarded as HTTP header)

    Returns:
        JSON object containing source, endpoint, count, and SRS certificate data
    """
    # Validate required parameters
    validate_string(officialnumber, "officialnumber", PATTERN_ALNUM, 1, 11)
    validate_string(vesselname, "vesselname", PATTERN_TEXT_WITH_SPACES, 1, 35)
    validate_string(registryportnumber, "registryportnumber", PATTERN_ALNUM, 1, 8)

    # Validate optional parameters if provided
    query_params = {
        "officialnumber": officialnumber,
        "vesselname": vesselname,
        "registryportnumber": registryportnumber,
    }

    if imonumber is not None:
        validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
        query_params["imonumber"] = imonumber

    if callsign is not None:
        validate_string(callsign, "callsign", PATTERN_ALNUM, 1, 8)
        query_params["callsign"] = callsign

    return fetch_json(
        BASE_URLS["srscor"],
        "/vesseldetails",
        apikey,
        "SRS Certificate by Vessel Details",
        query_params=query_params,
    )


def main() -> None:
    """Run the MCP server using streamable HTTP transport only."""
    mcp.run(
        transport=DEFAULT_TRANSPORT,
        host=HOST,
        port=PORT,
        path=MCP_HTTP_PATH,
    )


if __name__ == "__main__":
    main()
