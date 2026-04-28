# MPA Oceans-X MCP Server

A root-level FastMCP server for MPA Oceans-X APIs.

It wraps vessel schedule, port, port clearance, and vessel info endpoints from the MPA Oceans-X API as explicit MCP tools. The implementation lives at the `MCP-Server` root so API families can be added into one shared MCP server rather than creating separate per-folder servers.

## Overview

This server exposes maritime port authority information for Singapore through the Model Context Protocol (MCP). It acts as a bridge between MCP clients and the MPA Oceans-X REST APIs, providing real-time access to vessel schedules, positions, movements, port clearance records, and registration information. The server runs as a streamable HTTP MCP service, which is suitable for container hosting and remote MCP clients.

## Available Tools

The server provides 23 tools across 10 logical groups:

### Vessel Arrivals (Schedule)
- `get_vessel_arrivals_by_date` - Get vessel arrivals for a specific date
- `get_vessel_arrivals_past_hours` - Get vessel arrivals from the past N hours

### Vessels Due to Arrive (Schedule)
- `get_vessels_due_to_arrive_by_date` - Get vessels scheduled to arrive on a specific date
- `get_vessels_due_to_arrive_next_hours` - Get vessels scheduled to arrive in the next N hours

### Vessel Departures (Schedule)
- `get_vessel_departures_by_date` - Get vessel departures for a specific date
- `get_vessel_departures_past_hours` - Get vessel departures from the past N hours

### Vessels Due to Depart (Schedule)
- `get_vessels_due_to_depart_by_date` - Get vessels scheduled to depart on a specific date
- `get_vessels_due_to_depart_next_hours` - Get vessels scheduled to depart in the next N hours

### Vessel Movements & Positions (Port)
- `get_vessel_movements_by_imo` - Get vessel movement history by IMO number
- `get_vessel_positions_snapshot` - Get all vessel positions (current snapshot)
- `get_vessel_positions_by_imo` - Get vessel current position by IMO number

### Port Clearance Certificates (Port Clearance)
- `get_port_clearance_certificate_by_imo` - Get port clearance certificate by IMO number, GDV number, and certificate number

### Vessel Arrival Declarations (Port Clearance)
- `get_vessel_arrival_declaration_by_imo` - Get vessel arrival declaration by IMO number
- `get_latest_vessel_arrival_declaration_by_vessel_name` - Get the latest vessel arrival declaration by vessel name
- `get_vessel_arrival_declaration_by_date` - Get vessel arrival declarations by date
- `get_vessel_arrival_declaration_past_hours` - Get vessel arrival declarations for a date-time lookback window

### Vessel Departure Declarations (Port Clearance)
- `get_vessel_departure_declaration_by_imo` - Get vessel departure declaration by IMO number
- `get_vessel_departure_declarations_by_date` - Get vessel departure declarations by date
- `get_vessel_departure_declarations_past_hours` - Get vessel departure declarations for a date-time lookback window

### Vessel Particulars (Vessel Info)
- `get_vessel_particulars_by_name_pattern` - Search vessel particulars by vessel name pattern
- `get_vessel_particulars_by_imo` - Get vessel particulars by IMO number

### SRS Certificate (Vessel Info)
- `get_srs_certificate_by_certificate_number` - Get SRS certificate by certificate number
- `get_srs_certificate_by_vessel_details` - Get SRS certificate by vessel details (official number, name, port)

## Authentication

Clients must send an `apikey` HTTP header to the MCP server. The server reads that header from the incoming MCP request and forwards it to the upstream MPA Oceans-X API.

**Important:** The `apikey` is not stored by the server; it is only used to forward the request to the MPA API. Ensure that:
- The caller supplies a valid MPA API key
- The key is kept confidential
- Keys are rotated according to your security policy

## Tool Parameters

Schedule tools accept:
- `date` (string, required): Date in YYYY-MM-DD format
- `hours` (integer, required for hour-based tools): Positive integer representing lookback or lookahead window

Port tools accept:
- `imonumber` (string, required): IMO number of the vessel (1-10 chars, alphanumeric)

Port Clearance certificate tools accept:
- `imonumber` (string, required): IMO number of the vessel (1-10 chars, alphanumeric)
- `gdvno` (string, required): GDV number of the vessel (1-17 chars, alphanumeric)
- `certificateno` (string, required): Certificate ID (1-10 chars, alphanumeric)

Port Clearance arrival/departure declaration tools accept:
- IMO-based: `imonumber` (string, 1-10 chars, alphanumeric)
- Vessel-name latest arrival: `vesselname` (string, 1-35 chars, name pattern)
- Date-based: `date` (string, required): Date in YYYY-MM-DD format
- Past-hours based: `datetime_value` (string, required): Date-time in YYYY-MM-DD HH:MM:SS format
- Past-hours based: `hours` (string, required): 1-2 digits with optional decimal up to 2 places

Vessel Info tools accept:
- IMO-based: `imonumber` (string, 1-10 chars, alphanumeric)
- Name-based: `charset` (string, 3-8 chars, name pattern)
- Certificate-based: `certificatenumber` (string, 1-15 chars)
- Vessel details: `officialnumber`, `vesselname`, `registryportnumber` (required); `imonumber`, `callsign` (optional)

For all tools, the caller must include an `apikey` HTTP header in the MCP request.

## Response Format

All tools return a structured JSON object:

```json
{
  "source": "Logical API name",
  "endpoint": "Full upstream URL called",
  "count": 42,
  "data": [...]
}
```

- `source`: Human-readable name of the API
- `endpoint`: Full URL that was called upstream
- `count`: Number of records if response is a list; null otherwise
- `data`: Raw response from the upstream MPA API

## Running Locally

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
pip install -r requirements.txt
```

### Running the Server

```bash
python server.py
```

The server runs with streamable HTTP transport at `http://0.0.0.0:8000/mcp` by default.

## Environment Variables

Configure the server with these optional environment variables:

### Schedule API Base URLs
- `BASE_URL_ARRIVALS` - Override Vessel Arrivals API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/arrivals/1.0.0)
- `BASE_URL_DUE_TO_ARRIVE` - Override Vessels Due to Arrive API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/duetoarrive/1.0.0)
- `BASE_URL_DEPARTURES` - Override Vessel Departures API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/departure/1.0.0)
- `BASE_URL_DUE_TO_DEPART` - Override Vessels Due to Depart API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/duetodepart/1.0.0)

### Port API Base URLs
- `BASE_URL_MOVEMENTS` - Override Vessel Movements API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/movements/1.0.0)
- `BASE_URL_POSITIONS` - Override Vessel Positions API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/positions/1.0.0)

### Port Clearance API Base URLs
- `BASE_URL_PORT_CLEARANCE` - Override Port Clearance Certificate API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/portclearance/1.0.0)
- `BASE_URL_ARRIVAL_DECLARATION` - Override Vessel Arrival Declaration API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/arrivaldeclaration/1.0.0)
- `BASE_URL_DEPARTURE_DECLARATION` - Override Vessel Departure Declaration API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/departuredeclaration/1.0.0)

### Vessel Info API Base URLs
- `BASE_URL_PARTICULARS` - Override Vessel Particulars API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/particulars/1.0.0)
- `BASE_URL_SRSCOR` - Override SRS Certificate API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/srscor/1.0.0)

### Server Configuration
- `HTTP_TIMEOUT` - HTTP request timeout in seconds (default: 30.0)
- `HOST` - Bind address for the HTTP server (default: `0.0.0.0`)
- `PORT` - Port for the MCP HTTP endpoint / health endpoint (default: `8000`)
- `MCP_HTTP_PATH` - HTTP MCP path (default: `/mcp`)

Example (streamable HTTP transport):
```bash
export HOST=0.0.0.0
export PORT=8000
python server.py
```

## Docker

### Build the Docker Image

```bash
docker build -t mpa-ocx-mcp:latest .
```

### Run as a Container

Streamable HTTP transport:

```bash
docker run --rm -p 8000:8000 \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  mpa-ocx-mcp:latest
```

Health check:

```bash
curl http://localhost:8000/health
```

To pass additional environment variables:

```bash
docker run --rm -p 8000:8000 \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  -e HTTP_TIMEOUT=60 \
  mpa-ocx-mcp:latest
```

## MCP Client Configuration

### HTTP Streamable Transport

Run the server:

```bash
export HOST=0.0.0.0
export PORT=8000
python server.py
```

Then point your MCP client to:
- `http://localhost:8000/mcp`

If you deploy remotely, point the client to your deployed `/mcp` URL.

### Generic MCP Configuration

Use your MCP client's HTTP configuration to connect to the `/mcp` endpoint. Example shape:

```json
{
  "mcpServers": {
    "mpa-ocx": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "apikey": "YOUR_MPA_API_KEY"
      }
    }
  }
}
```

### Using with Other MCP Clients

Refer to your MCP client's documentation for configuring streamable HTTP MCP servers. This server exposes a health endpoint at `/health` and the MCP endpoint at `/mcp`.

## Error Handling

The server validates inputs and returns meaningful errors:

- **Invalid date format**: Returns `ValueError` with message "date must be in YYYY-MM-DD format"
- **Invalid hours**: Returns `ValueError` with message "hours must be a positive integer"
- **Upstream API error**: Returns `RuntimeError` with HTTP status code and error body snippet

## Azure Container Apps Deployment

This project is containerized and ready for Azure Container Apps.

Recommended deployment mode for ACA:
1. Run the container and expose port `8000`
2. Use `/health` as the liveness/readiness probe path
3. Use `/mcp` as the MCP HTTP endpoint

Example runtime environment variables:

```text
HOST=0.0.0.0
PORT=8000
MCP_HTTP_PATH=/mcp
HTTP_TIMEOUT=30
```

## Development

### Project Structure

- `server.py` - FastMCP server implementation with 23 tools
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container image definition
- `.dockerignore` - Files excluded from Docker image
- `IMPLEMENTATION_PLAN.md` - Implementation guidelines and API reference
- `Schedule/*.json` - Schedule OpenAPI source specifications (Arrivals, Departures, Due to Arrive/Depart)
- `Port/*.json` - Port OpenAPI source specifications (Vessel Movements, Vessel Positions)
- `Port Clearance/*.json` - Port Clearance OpenAPI source specifications (Certificates, Arrival Declarations, Departure Declarations)
- `Vessel Info/*.json` - Vessel Info OpenAPI source specifications (Vessel Particulars, SRS Certificates)

### Code Layout

The `server.py` is organized into these main sections:

1. **Configuration & Regex Patterns**: Base URLs, transport settings, precompiled regex patterns
2. **Helpers**: Validation functions, HTTP client wrapper, response formatting
3. **Tools**: 23 explicit MCP tool functions organized by API domain
   - Schedule (8 tools)
   - Vessel Movements & Positions (3 tools)
  - Port Clearance (8 tools)
   - Vessel Particulars (2 tools)
   - SRS Certificates (2 tools)
4. **Entrypoint**: `main()` runs the MCP server with streamable HTTP transport only

### Adding New Endpoints

To add a new endpoint:

1. Add the base URL to `BASE_URLS` dictionary
2. Create a new tool function decorated with `@mcp.tool()`
3. Include validation calls for parameters
4. Return structured JSON via `fetch_json()`

## License

Internal MPA use.

## Support

For issues or questions, contact the development team.
