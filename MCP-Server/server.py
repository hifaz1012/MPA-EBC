#!/usr/bin/env python3
"""
Root MCP server for MPA Oceans-X APIs.

Wraps vessel schedule, port, port clearance, and vessel info endpoints from MPA Oceans-X as MCP tools.
The server lives at the MCP-Server root so API groups can be added into one shared
MCP server over time. Each tool forwards the apikey header token to the upstream API.
"""

import os
import re
from datetime import datetime
from typing import Any, Optional

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SERVER_INSTRUCTIONS = (
    "Root MPA Oceans-X MCP server exposing vessel schedule, port, port clearance, and "
    "vessel info lookups over streamable HTTP. Provides Schedule (arrivals, departures, "
    "due-to-arrive/depart), Port (vessel movements and positions), Port Clearance "
    "(certificates and arrival/departure declarations), and Vessel Info (vessel "
    "particulars and SRS certificate) tools. Clients must send an `apikey` HTTP header "
    "to this MCP server, and the server forwards that value to the upstream MPA Oceans-X "
    "API as the `apikey` HTTP header. Use YYYY-MM-DD dates and positive integer hours for "
    "hour-based queries unless a tool explicitly accepts a date-time string."
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
    # Port Clearance
    "port_clearance": os.getenv("BASE_URL_PORT_CLEARANCE", "https://oceans-x.mpa.gov.sg/api/v1/vessel/portclearance/1.0.0"),
    "arrival_declaration": os.getenv("BASE_URL_ARRIVAL_DECLARATION", "https://oceans-x.mpa.gov.sg/api/v1/vessel/arrivaldeclaration/1.0.0"),
    "departure_declaration": os.getenv("BASE_URL_DEPARTURE_DECLARATION", "https://oceans-x.mpa.gov.sg/api/v1/vessel/departuredeclaration/1.0.0"),
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
PATTERN_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
PATTERN_LOOKBACK_HOURS = re.compile(r"^[\d]{1,2}(\.\d{1,2})?$")



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


def validate_datetime_string(datetime_str: str) -> None:
    """Validate datetime format (YYYY-MM-DD HH:MM:SS)."""
    validate_string(datetime_str, "datetime", PATTERN_DATETIME, 19, 19)
    try:
        datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError("datetime must be in YYYY-MM-DD HH:MM:SS format")


def validate_hours_string(hours: str) -> None:
    """Validate string hours for APIs that accept 1-2 digits with optional decimals."""
    validate_string(hours, "hours", PATTERN_LOOKBACK_HOURS, 1, 5)


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


def get_request_apikey() -> str:
    """Read the apikey from the incoming MCP HTTP request headers."""
    headers = get_http_headers()
    apikey = headers.get("apikey")
    validate_apikey(apikey)
    return apikey


def fetch_json(
    base_url: str,
    path: str,
    source: str,
    query_params: Optional[dict] = None,
) -> dict:
    """
    Fetch JSON from upstream API.

    Args:
        base_url: Base URL of the upstream API
        path: Path to append to base URL
        source: Logical API name for response
        query_params: Optional dict of query parameters

    Returns:
        Structured JSON response with source, endpoint, count, and data

    Raises:
        ValueError: If the request apikey or parameters are invalid
        RuntimeError: If upstream returns non-2xx status or connection fails
    """
    apikey = get_request_apikey()
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
def get_vessel_arrivals_by_date(date: str) -> dict:
    """
    Get vessel arrivals by date.

    Provides vessel arrival information for a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")

    Returns:
        JSON object containing source, endpoint, count, and arrival data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["arrivals"],
        f"/date/{date}",
        "Vessel Arrivals"
    )


@mcp.tool()
def get_vessel_arrivals_past_hours(date: str, hours: int) -> dict:
    """
    Get vessel arrivals for past N hours.

    Returns vessel arrivals for a given date and lookback hours in YYYY-MM-DD format.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of past hours to include (positive integer)

    Returns:
        JSON object containing source, endpoint, count, and arrival data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["arrivals"],
        f"/date/{date}/hours/{hours}",
        "Vessel Arrivals (Past Hours)"
    )


# ============================================================================
# Vessels Due to Arrive Tools
# ============================================================================

@mcp.tool()
def get_vessels_due_to_arrive_by_date(date: str) -> dict:
    """
    Get vessels due to arrive by date.

    Provides vessel information for vessels due to arrive on a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")

    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["due_to_arrive"],
        f"/date/{date}",
        "Vessels Due to Arrive"
    )


@mcp.tool()
def get_vessels_due_to_arrive_next_hours(date: str, hours: int) -> dict:
    """
    Get vessels due to arrive for next N hours.

    Returns vessels due to arrive within a specified number of hours from a given date in YYYY-MM-DD format.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of hours ahead to include (positive integer)

    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["due_to_arrive"],
        f"/date/{date}/hours/{hours}",
        "Vessels Due to Arrive (Next Hours)"
    )


# ============================================================================
# Vessel Departures Tools
# ============================================================================

@mcp.tool()
def get_vessel_departures_by_date(date: str) -> dict:
    """
    Get vessel departures by date.

    Provides vessel departure information for a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")

    Returns:
        JSON object containing source, endpoint, count, and departure data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["departures"],
        f"/date/{date}",
        "Vessel Departures"
    )


@mcp.tool()
def get_vessel_departures_past_hours(date: str, hours: int) -> dict:
    """
    Get vessel departures for past N hours.

    Returns vessel departures for a given date and lookback hours in YYYY-MM-DD format.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of past hours to include (positive integer)

    Returns:
        JSON object containing source, endpoint, count, and departure data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["departures"],
        f"/date/{date}/hours/{hours}",
        "Vessel Departures (Past Hours)"
    )


# ============================================================================
# Vessels Due to Depart Tools
# ============================================================================

@mcp.tool()
def get_vessels_due_to_depart_by_date(date: str) -> dict:
    """
    Get vessels due to depart by date.

    Provides vessel information for vessels due to depart on a given date in YYYY-MM-DD format.
    Upstream data is updated every hour.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")

    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["due_to_depart"],
        f"/date/{date}",
        "Vessels Due to Depart"
    )


@mcp.tool()
def get_vessels_due_to_depart_next_hours(date: str, hours: int) -> dict:
    """
    Get vessels due to depart for next N hours.

    Returns vessels due to depart within a specified number of hours from a given date in YYYY-MM-DD format.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-08-30")
        hours: Number of hours ahead to include (positive integer)

    Returns:
        JSON object containing source, endpoint, count, and vessel data
    """
    validate_date(date)
    validate_hours(hours)
    return fetch_json(
        BASE_URLS["due_to_depart"],
        f"/date/{date}/hours/{hours}",
        "Vessels Due to Depart (Next Hours)"
    )




# ============================================================================
# Vessel Positions Tools
# ============================================================================

@mcp.tool()
def get_vessel_positions_snapshot() -> dict:
    """
    Get all vessel positions (snapshot).

    Returns a snapshot of current positions for all vessels in the port area.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Returns:
        JSON object containing source, endpoint, count, and position data
    """
    return fetch_json(
        BASE_URLS["positions"],
        "/snapshot",
        "Vessel Positions (Snapshot)"
    )


@mcp.tool()
def get_vessel_positions_by_imo(imonumber: str) -> dict:
    """
    Get vessel positions by IMO number.

    Retrieves current position information for a specific vessel identified by IMO number.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        imonumber: IMO number of the vessel (1-10 characters, alphanumeric)

    Returns:
        JSON object containing source, endpoint, count, and position data
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["positions"],
        f"/imonumber/{imonumber}",
        "Vessel Positions by IMO"
    )


@mcp.tool()
def get_vessel_movements_by_imo(imonumber: str) -> dict:
    """
    Get vessel movements by IMO number.

    Retrieves movement history for a specific vessel identified by IMO number.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        imonumber: IMO number of the vessel (1-10 characters, alphanumeric)

    Returns:
        JSON object containing source, endpoint, count, and movement data
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["movements"],
        f"/imonumber/{imonumber}",
        "Vessel Movements by IMO"
    )


# ============================================================================
# Port Clearance Tools
# ============================================================================

@mcp.tool()
def get_port_clearance_certificate_by_imo(
    imonumber: str,
    gdvno: str,
    certificateno: str,
) -> dict:
    """
    Get port clearance certificate by IMO number.

    Provides the corresponding port clearance certificate information for the given vessel
    IMO number, GDV number, and certificate number. The data is updated every hour.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        imonumber: IMO number of vessel (1-10 alphanumeric characters)
        gdvno: GDV number of the vessel (1-17 alphanumeric characters)
        certificateno: Certificate ID (1-10 alphanumeric characters)

    Returns:
        JSON object containing source, endpoint, count, and port clearance certificate data
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    validate_string(gdvno, "gdvno", PATTERN_ALNUM, 1, 17)
    validate_string(certificateno, "certificateno", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["port_clearance"],
        f"/imonumber/{imonumber}",
        "Port Clearance Certificate by IMO",
        query_params={"gdvno": gdvno, "certificateno": certificateno},
    )


@mcp.tool()
def get_vessel_arrival_declaration_by_imo(imonumber: str) -> dict:
    """
    Get vessel arrival declaration by IMO number.

    Provides the corresponding vessel arrival declaration information for the given vessel
    IMO number. The data is updated every hour. The MCP request must include an 'apikey'
    HTTP header, which is forwarded upstream.

    Args:
        imonumber: IMO number of vessel (1-10 alphanumeric characters)

    Returns:
        JSON object containing source, endpoint, count, and arrival declaration data
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["arrival_declaration"],
        f"/imonumber/{imonumber}",
        "Vessel Arrival Declaration by IMO",
    )


@mcp.tool()
def get_latest_vessel_arrival_declaration_by_vessel_name(vesselname: str) -> dict:
    """
    Get latest vessel arrival declaration by vessel name.

    Provides the corresponding latest vessel arrival declaration information for the given
    vessel name. The data is updated every hour. The MCP request must include an 'apikey'
    HTTP header, which is forwarded upstream.

    Args:
        vesselname: Vessel name (1-35 characters, alphanumeric plus punctuation and spaces)

    Returns:
        JSON object containing source, endpoint, count, and arrival declaration data
    """
    validate_string(vesselname, "vesselname", PATTERN_TEXT_WITH_SPACES, 1, 35)
    return fetch_json(
        BASE_URLS["arrival_declaration"],
        f"/last/vesselname/{vesselname}",
        "Latest Vessel Arrival Declaration by Vessel Name",
    )


@mcp.tool()
def get_vessel_arrival_declaration_by_date(date: str) -> dict:
    """
    Get vessel arrival declaration by date.

    Provides the corresponding vessel arrival declaration information for the given date.
    The data is updated every hour. The MCP request must include an 'apikey' HTTP header,
    which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        JSON object containing source, endpoint, count, and arrival declaration data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["arrival_declaration"],
        "/bydate",
        "Vessel Arrival Declaration by Date",
        query_params={"date": date},
    )


@mcp.tool()
def get_vessel_arrival_declaration_past_hours(datetime_value: str, hours: str) -> dict:
    """
    Get vessel arrival declaration for past N hours.

    Provides the corresponding vessels arrival declaration information for the given date
    and time. The data is updated every hour. The MCP request must include an 'apikey'
    HTTP header, which is forwarded upstream.

    Args:
        datetime_value: Date and time in YYYY-MM-DD HH:MM:SS format
        hours: Number of past hours to query (1-2 digits, optional decimal with up to 2 digits)

    Returns:
        JSON object containing source, endpoint, count, and arrival declaration data
    """
    validate_datetime_string(datetime_value)
    validate_hours_string(hours)
    return fetch_json(
        BASE_URLS["arrival_declaration"],
        "/pastNhours",
        "Vessel Arrival Declaration (Past Hours)",
        query_params={"datetime": datetime_value, "hours": hours},
    )


@mcp.tool()
def get_vessel_departure_declaration_by_imo(imonumber: str) -> dict:
    """
    Get vessel departure declaration by IMO number.

    Provides the vessel departure declaration information for the given vessel IMO number.
    Data is updated hourly. The MCP request must include an 'apikey' HTTP header, which is
    forwarded upstream.

    Args:
        imonumber: IMO number of vessel (1-10 alphanumeric characters)

    Returns:
        JSON object containing source, endpoint, count, and departure declaration data
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["departure_declaration"],
        f"/imonumber/{imonumber}",
        "Vessel Departure Declaration by IMO",
    )


@mcp.tool()
def get_vessel_departure_declarations_by_date(date: str) -> dict:
    """
    Get vessel departure declarations by date.

    Provides all vessel departure declarations for a specific date. Data is updated hourly.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        JSON object containing source, endpoint, count, and departure declaration data
    """
    validate_date(date)
    return fetch_json(
        BASE_URLS["departure_declaration"],
        "/bydate",
        "Vessel Departure Declarations by Date",
        query_params={"date": date},
    )


@mcp.tool()
def get_vessel_departure_declarations_past_hours(datetime_value: str, hours: str) -> dict:
    """
    Get vessel departure declarations for past N hours.

    Provides all vessel departure declarations for the past N hours. Data is updated hourly.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        datetime_value: Date and time in YYYY-MM-DD HH:MM:SS format
        hours: Number of past hours to query (1-2 digits, optional decimal with up to 2 digits)

    Returns:
        JSON object containing source, endpoint, count, and departure declaration data
    """
    validate_datetime_string(datetime_value)
    validate_hours_string(hours)
    return fetch_json(
        BASE_URLS["departure_declaration"],
        "/pastNhours",
        "Vessel Departure Declarations (Past Hours)",
        query_params={"datetime": datetime_value, "hours": hours},
    )


# ============================================================================
# Vessel Particulars Tools
# ============================================================================

@mcp.tool()
def get_vessel_particulars_by_name_pattern(charset: str) -> dict:
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
    Returns:
        JSON object containing source, endpoint, count, and vessel particulars
    """
    validate_string(charset, "charset", PATTERN_TEXT_WITH_SPACES, 3, 8)
    return fetch_json(
        BASE_URLS["particulars"],
        f"/name/{charset}",
        "Vessel Particulars by Name Pattern"
    )


@mcp.tool()
def get_vessel_particulars_by_imo(imonumber: str) -> dict:
    """
    Get vessel particulars by IMO number.

    Retrieves detailed information about a specific vessel identified by IMO number.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        imonumber: IMO number of the vessel (1-10 characters, alphanumeric)

    Returns:
        JSON object containing source, endpoint, count, and vessel particulars
    """
    validate_string(imonumber, "imonumber", PATTERN_ALNUM, 1, 10)
    return fetch_json(
        BASE_URLS["particulars"],
        f"/imonumber/{imonumber}",
        "Vessel Particulars by IMO"
    )


# ============================================================================
# SRS Certificate Tools
# ============================================================================

@mcp.tool()
def get_srs_certificate_by_certificate_number(certificatenumber: str) -> dict:
    """
    Get SRS certificate by certificate number.

    Retrieves the SRS (Singapore Registry of Ships) Certificate of Registry by its certificate number.
    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        certificatenumber: Certificate number (1-15 characters, alphanumeric + hyphens, underscores, periods, spaces, apostrophes)

    Returns:
        JSON object containing source, endpoint, count, and SRS certificate data
    """
    validate_string(certificatenumber, "certificatenumber", PATTERN_TEXT_WITH_SPACES, 1, 15)
    return fetch_json(
        BASE_URLS["srscor"],
        f"/certificatenumber/{certificatenumber}",
        "SRS Certificate by Certificate Number"
    )


@mcp.tool()
def get_srs_certificate_by_vessel_details(
    officialnumber: str,
    vesselname: str,
    registryportnumber: str,
    imonumber: Optional[str] = None,
    callsign: Optional[str] = None,
) -> dict:
    """
    Get SRS certificate by vessel details.

    Retrieves the SRS (Singapore Registry of Ships) Certificate of Registry using vessel details.
    Three parameters are required: official number, vessel name, and registry port number.
    IMO number and call sign are optional for narrowing results.

    The MCP request must include an 'apikey' HTTP header, which is forwarded upstream.

    Args:
        officialnumber: Official vessel number (1-11 characters, alphanumeric) [required]
        vesselname: Vessel name (1-35 characters, alphanumeric + hyphens, underscores, periods, spaces, apostrophes) [required]
        registryportnumber: Registry port number (1-8 characters, alphanumeric) [required]
        imonumber: IMO number (1-10 characters, alphanumeric) [optional]
        callsign: Call sign (1-8 characters, alphanumeric) [optional]

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
