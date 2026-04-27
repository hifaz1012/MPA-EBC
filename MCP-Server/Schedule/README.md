# MPA Schedule MCP Server

A FastMCP server that wraps all 8 vessel schedule endpoints from the MPA Oceans-X API as explicit MCP tools.

## Overview

This server exposes vessel schedule information for Singapore's Maritime Port Authority (MPA) through the Model Context Protocol (MCP). It acts as a bridge between MCP clients and the MPA Oceans-X REST APIs.

## Available Tools

The server provides 8 tools across 4 logical groups:

### Vessel Arrivals
- `get_vessel_arrivals_by_date` - Get vessel arrivals for a specific date
- `get_vessel_arrivals_past_hours` - Get vessel arrivals from the past N hours

### Vessels Due to Arrive
- `get_vessels_due_to_arrive_by_date` - Get vessels scheduled to arrive on a specific date
- `get_vessels_due_to_arrive_next_hours` - Get vessels scheduled to arrive in the next N hours

### Vessel Departures
- `get_vessel_departures_by_date` - Get vessel departures for a specific date
- `get_vessel_departures_past_hours` - Get vessel departures from the past N hours

### Vessels Due to Depart
- `get_vessels_due_to_depart_by_date` - Get vessels scheduled to depart on a specific date
- `get_vessels_due_to_depart_next_hours` - Get vessels scheduled to depart in the next N hours

## Authentication

Each tool requires an `apikey` parameter. The server forwards this value as the `apikey` HTTP header to the upstream MPA Oceans-X API.

**Important:** The `apikey` is not stored by the server; it is only used to forward the request to the MPA API. Ensure that:
- The caller supplies a valid MPA API key
- The key is kept confidential
- Keys are rotated according to your security policy

## Tool Parameters

All tools accept:
- `date` (string, required): Date in YYYY-MM-DD format
- `hours` (integer, required for hour-based tools): Positive integer representing lookback or lookahead window
- `apikey` (string, required): MPA API key (forwarded as HTTP header)

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

The server will start using stdio transport (suitable for MCP clients that can launch stdio processes).

## Environment Variables

Configure the server with these optional environment variables:

- `BASE_URL_ARRIVALS` - Override Vessel Arrivals API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/arrivals/1.0.0)
- `BASE_URL_DUE_TO_ARRIVE` - Override Vessels Due to Arrive API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/duetoarrive/1.0.0)
- `BASE_URL_DEPARTURES` - Override Vessel Departures API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/departure/1.0.0)
- `BASE_URL_DUE_TO_DEPART` - Override Vessels Due to Depart API base URL (default: https://oceans-x.mpa.gov.sg/api/v1/vessel/duetodepart/1.0.0)
- `HTTP_TIMEOUT` - HTTP request timeout in seconds (default: 30.0)
- `MCP_TRANSPORT` - FastMCP transport to run (`stdio` by default, or `http`, `streamable-http`, `sse`)
- `HOST` - Bind address for HTTP transport (default: `0.0.0.0`)
- `PORT` - Port for HTTP transport / health endpoint (default: `8000`)
- `MCP_HTTP_PATH` - HTTP MCP path when using HTTP transport (default: `/mcp`)

Example (stdio):
```bash
export HTTP_TIMEOUT=60
python server.py
```

Example (HTTP for container platforms):
```bash
export MCP_TRANSPORT=http
export HOST=0.0.0.0
export PORT=8000
python server.py
```

## Docker

### Build the Docker Image

```bash
docker build -t mpa-schedule-mcp:latest .
```

### Run as a Container

Default stdio mode:

```bash
docker run --rm mpa-schedule-mcp:latest
```

HTTP mode for Azure Container Apps or other container platforms:

```bash
docker run --rm -p 8000:8000 \
  -e MCP_TRANSPORT=http \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  mpa-schedule-mcp:latest
```

Health check:

```bash
curl http://localhost:8000/health
```

To pass additional environment variables:

```bash
docker run --rm \
  -e MCP_TRANSPORT=http \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  -e HTTP_TIMEOUT=60 \
  mpa-schedule-mcp:latest
```

## MCP Client Configuration

### Using with Hermes

```bash
hermes mcp add mpa-schedule \
  --command python \
  --args /home/marcus/MPA-EBC/MCP-Server/Schedule/server.py
```

Or use Docker in stdio mode:

```bash
hermes mcp add mpa-schedule-docker \
  --command docker \
  --args run --rm mpa-schedule-mcp:latest
```

### Generic MCP JSON Configuration

```json
{
  "mcpServers": {
    "mpa-schedule": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {}
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "mpa-schedule": {
      "command": "docker",
      "args": ["run", "--rm", "mpa-schedule-mcp:latest"]
    }
  }
}
```

### Using with Other MCP Clients

Refer to your MCP client's documentation for configuring stdio-based MCP servers. The `server.py` script defaults to stdio transport, making it compatible with MCP clients that support stdio transport. For HTTP deployments, set `MCP_TRANSPORT=http` and point compatible clients to the `/mcp` endpoint.

## Error Handling

The server validates inputs and returns meaningful errors:

- **Invalid date format**: Returns `ValueError` with message "date must be in YYYY-MM-DD format"
- **Invalid hours**: Returns `ValueError` with message "hours must be a positive integer"
- **Upstream API error**: Returns `RuntimeError` with HTTP status code and error body snippet

## Azure Container Apps Deployment

This project is ready to containerize for Azure Container Apps.

Recommended deployment mode for ACA:
1. run the container with `MCP_TRANSPORT=http`
2. expose port `8000`
3. use `/health` as the liveness/readiness probe path
4. use `/mcp` as the MCP HTTP endpoint

Example runtime environment variables:

```text
MCP_TRANSPORT=http
HOST=0.0.0.0
PORT=8000
MCP_HTTP_PATH=/mcp
HTTP_TIMEOUT=30
```

Important note:
- If your MCP client can spawn stdio servers directly, stdio is the simplest integration.
- If you want the server hosted remotely in ACA, use the HTTP transport mode above so clients can connect over HTTP.

## Development

### Project Structure

- `server.py` - FastMCP server implementation
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container image definition
- `.dockerignore` - Files excluded from Docker image
- `IMPLEMENTATION_PLAN.md` - Implementation guidelines
- OpenAPI JSON files - Source specifications for the APIs

### Code Layout

The `server.py` is organized into three main sections:

1. **Configuration & Helpers**: Base URLs, validation, HTTP client
2. **Tools**: Eight explicit MCP tool functions grouped by API domain
3. **Entrypoint**: `if __name__ == "__main__"` runs the MCP stdio server

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
