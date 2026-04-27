# Schedule FastMCP Server Implementation Plan

> **For Hermes/Copilot:** implement a Python FastMCP server in this folder that exposes MCP tools derived from the Schedule OpenAPI specifications.

**Goal:** Build a container-ready Python FastMCP server for the `Schedule` APIs that forwards an `apikey` header token from the MCP caller to the upstream MPA Oceans-X HTTP APIs.

**Architecture:** Use a small FastMCP app with explicit tool functions instead of trying to dynamically serve raw OpenAPI. The OpenAPI files in this folder define 8 GET endpoints across 4 schedule domains; the MCP server should wrap them as well-described tools, validate inputs, inject the `apikey` header supplied by the caller, call the upstream REST endpoints with `httpx`, and return structured JSON. Package it with `requirements.txt`, `README.md`, and a Dockerfile suitable for Azure Container Apps.

**Tech Stack:** Python 3.11, fastmcp, httpx, pydantic, uvicorn (optional runtime helper)

---

## OpenAPI findings

The `Schedule` folder contains 8 Swagger/OpenAPI JSON files representing 4 logical API groups:

1. **Vessel Arrivals**
   - `Vessel Arrivals_swagger.json`: `GET /date/{date}`
   - `Vessel Arrivals_swagger copy.json`: `GET /date/{date}/hours/{hours}`
   - Base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/arrivals/1.0.0`

2. **Vessels Due to Arrive**
   - `Vessels Due to Arrive_swagger.json`: `GET /date/{date}`
   - `Vessels Due to Arrive_swagger (1).json`: `GET /date/{date}/hours/{hours}`
   - Base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/duetoarrive/1.0.0`

3. **Vessel Departures**
   - `Vessel Departures_swagger.json`: `GET /date/{date}`
   - `Vessel Departures_swagger (1).json`: `GET /date/{datetime}/hours/{hours}`
   - Base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/departure/1.0.0`

4. **Vessels Due to Depart**
   - `Vessels Due to Depart_swagger.json`: `GET /date/{date}`
   - `Vessels Due to Depart_swagger (1).json`: `GET /date/{datetime}/hours/{hours}`
   - Base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/duetodepart/1.0.0`

Authentication in all specs is the same:
- security scheme: `api_key`
- header name: `apikey`
- location: `header`

## Best implementation approach

### Why not a fully generic OpenAPI-to-MCP runtime?
A generic runtime converter would add complexity without much value here because:
- only 8 endpoints exist,
- all are simple GET endpoints,
- all require the same auth pattern,
- good MCP descriptions matter, and
- explicit tools make the server easier to test, document, and maintain.

### Recommended shape
Create an MCP server with:
- one shared HTTP client helper,
- one shared date validator,
- one shared token/header injection helper,
- 8 explicit MCP tools, each mirroring one OpenAPI operation,
- rich docstrings/descriptions from the OpenAPI summaries/descriptions,
- env-configurable base URLs and timeout,
- Docker-friendly stdio entrypoint.

### Tool design rule
Each MCP tool must accept `apikey: str` as an argument because the user wants the MCP server to expect a header token and pass it through to the upstream API for authentication. Since standard FastMCP tools are function-based, model this as a required tool parameter named `apikey`, document clearly that it is forwarded as the HTTP header `apikey`, and avoid storing secrets in the server.

### Output design rule
Return a JSON object shaped like:
- `source`: logical API name
- `endpoint`: fully resolved upstream URL
- `count`: number of returned records if response is a list, else null
- `data`: upstream JSON body

This makes downstream agent usage easier than returning raw text.

---

## Files to create

- `server.py` — main FastMCP server
- `requirements.txt` — Python dependencies
- `README.md` — usage, auth, Docker, Azure Container Apps notes
- `Dockerfile` — container image for Azure Container Apps
- `.dockerignore` — avoid copying noise into the image

## Implementation details Copilot should follow

### `server.py`
Implement:
- `mcp = FastMCP("mpa-schedule-mcp", instructions=...)`
- constants for each upstream base URL
- `validate_date(date_str: str)` using `datetime.strptime(..., "%Y-%m-%d")`
- `build_headers(apikey: str) -> dict` returns `{"apikey": apikey, "Accept": "application/json"}`
- `fetch_json(base_url: str, path: str, apikey: str) -> dict`
  - use `httpx.Client(timeout=...)`
  - call `raise_for_status()`
  - parse `response.json()`
  - wrap into structured return object
- 8 tool functions:
  - `get_vessel_arrivals_by_date`
  - `get_vessel_arrivals_past_hours`
  - `get_vessels_due_to_arrive_by_date`
  - `get_vessels_due_to_arrive_next_hours`
  - `get_vessel_departures_by_date`
  - `get_vessel_departures_past_hours`
  - `get_vessels_due_to_depart_by_date`
  - `get_vessels_due_to_depart_next_hours`
- Each tool must:
  - include a precise description based on the OpenAPI summary/description,
  - validate date format,
  - validate hours is positive integer where relevant,
  - pass the token as header `apikey`,
  - return structured JSON.
- Add a `main()` that runs stdio transport so it works as an MCP server in containers.

### Descriptions to preserve/improve
Use descriptions similar to:
- “Get vessel arrivals by date. Provides vessel arrival information for a given date in yyyy-MM-dd format. Upstream data is updated every hour.”
- “Get vessel arrivals for past N hours from a given date. Passes the provided `apikey` value to the upstream MPA API as the `apikey` HTTP header.”

Do the same for all 8 tools.

### Error handling
Map failures into readable exceptions:
- invalid date -> `ValueError("date must be in YYYY-MM-DD format")`
- invalid hours -> `ValueError("hours must be a positive integer")`
- upstream non-2xx -> raise `RuntimeError` containing status code and body snippet

### `requirements.txt`
Include only what is needed:
- `fastmcp`
- `httpx`
- `pydantic`

### `README.md`
Include:
- what the server does
- list of 8 tools
- auth model: caller supplies `apikey` tool argument; server forwards it as HTTP header `apikey`
- local run example
- sample Hermes MCP config using stdio command
- docker build/run examples
- Azure Container Apps note: deploy as container, but MCP stdio works best when used by clients that can launch the containerized process or by wrapping with an MCP transport bridge later if HTTP transport is needed.

### `Dockerfile`
Use a slim Python base image:
- `python:3.11-slim`
- install deps from `requirements.txt`
- copy project files
- set `PYTHONUNBUFFERED=1`
- command should run the MCP server process

### `.dockerignore`
Ignore:
- `__pycache__/`
- `*.pyc`
- `.git`
- `.venv`
- local swagger duplicates only if you intentionally do not need them in image; otherwise keep them out of ignore

---

## Quality bar
Before calling implementation complete, verify:
1. all 8 operations from the OpenAPI files exist as MCP tools;
2. every tool has a meaningful description;
3. every tool accepts `apikey` and forwards it as header `apikey`;
4. dates/hours are validated;
5. files `server.py`, `requirements.txt`, `README.md`, `Dockerfile`, `.dockerignore` exist;
6. code is understandable and not over-engineered for this first version.
