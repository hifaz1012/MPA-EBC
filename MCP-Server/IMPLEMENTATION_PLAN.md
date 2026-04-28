# MPA Oceans-X Root MCP Server Expansion Plan

> Historical plan and implementation brief for expanding the root `MCP-Server` FastMCP service beyond Schedule.

**Goal:** Extend the root Python FastMCP server to include all APIs currently available under `Port/` and `Vessel Info/`, while keeping the code simple, explicit, and HTTP streamable only.

**Architecture:** Keep a single root `server.py` with small shared helpers for validation, HTTP requests, and structured JSON responses. Continue the explicit-tool approach instead of building a generic OpenAPI runtime converter, because the current APIs are a manageable set of simple GET endpoints with shared authentication. Run only as an HTTP MCP server using streamable HTTP transport; do not keep stdio mode.

**Tech Stack:** Python 3.11, fastmcp, httpx, pydantic

---

## OpenAPI findings

### Shared auth pattern
All inspected specs use the same authentication model:
- security scheme: `api_key`
- header name: `apikey`
- location: `header`

### Existing Schedule tools already wrapped
The root server already wraps the 8 Schedule endpoints under `Schedule/`.

### Port APIs to add

1. **Vessel Movements**
   - file: `Port/Vessel Movements_swagger.json`
   - base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/movements/1.0.0`
   - endpoint: `GET /imonumber/{imonumber}`
   - summary: `Get vessel movements by IMO number`
   - param: `imonumber` (path, string, 1-10 chars, pattern `^[a-zA-Z0-9]+$`)

2. **Vessel Positions**
   - file: `Port/Vessel Positions_swagger.json`
   - base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/positions/1.0.0`
   - endpoint: `GET /snapshot`
   - summary: `Get all vessel positions (snapshot)`
   - params: none besides `apikey`

3. **Vessel Positions by IMO**
   - file: `Port/Vessel Positions_swagger (1).json`
   - base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/positions/1.0.0`
   - endpoint: `GET /imonumber/{imonumber}`
   - summary: `Get vessel positions by IMO number`
   - param: `imonumber` (path, string, 1-10 chars, pattern `^[a-zA-Z0-9]+$`)

### Vessel Info APIs to add

4. **Vessel Particulars by Name Pattern**
   - file: `Vessel Info/Vessel Particulars_swagger.json`
   - base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/particulars/1.0.0`
   - endpoint: `GET /name/{charset}`
   - summary: `Get vessel particulars by vessel name pattern`
   - param: `charset` (path, string, 3-8 chars, pattern `^[0-9a-zA-Z-_. ']+$`)

5. **Vessel Particulars by IMO**
   - file: `Vessel Info/Vessel Particulars_swagger (1).json`
   - base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/particulars/1.0.0`
   - endpoint: `GET /imonumber/{imonumber}`
   - summary: `Get vessel particulars by IMO number`
   - param: `imonumber` (path, string, 1-10 chars, pattern `^[a-zA-Z0-9]+$`)

6. **SRS Certificate by Certificate Number**
   - file: `Vessel Info/SRS Certificate of Registry_swagger.json`
   - base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/srscor/1.0.0`
   - endpoint: `GET /certificatenumber/{certificatenumber}`
   - summary: `Get SRS certificate by certificate number`
   - param: `certificatenumber` (path, string, 1-15 chars, pattern `^[0-9a-zA-Z-_. ']+$`)

7. **SRS Certificate by Vessel Details**
   - file: `Vessel Info/SRS Certificate of Registry_swagger (1).json`
   - base URL: `https://oceans-x.mpa.gov.sg/api/v1/vessel/srscor/1.0.0`
   - endpoint: `GET /vesseldetails`
   - summary: `Get SRS certificate by vessel details`
   - required query params:
     - `officialnumber` (1-11 chars, `^[a-zA-Z0-9]+$`)
     - `vesselname` (1-35 chars, `^[0-9a-zA-Z-_. ']+$`)
     - `registryportnumber` (1-8 chars, `^[a-zA-Z0-9]+$`)
   - optional query params:
     - `imonumber` (1-10 chars, `^[a-zA-Z0-9]+$`)
     - `callsign` (1-8 chars, `^[a-zA-Z0-9]+$`)

---

## Recommended implementation shape

### Keep it explicit and simple
Use explicit tool functions in `server.py` for each new operation. Avoid dynamic registration, metaprogramming, or spec parsing at runtime.

### Shared helpers to keep code clean
Use or add small reusable helpers for:
- `build_headers(apikey)`
- path/query validation with regex and length checks
- `fetch_json(base_url, path, apikey, source, query_params=None)`
- consistent structured JSON response shape

### Root server description
Update the FastMCP instructions so the MCP server description clearly states:
- this is the root MPA Oceans-X MCP server
- it currently covers Schedule, Port, and Vessel Info lookups
- every tool requires an `apikey` argument forwarded as the `apikey` HTTP header
- the server is exposed via HTTP streamable MCP transport

### Transport requirement
Remove stdio behavior. The server should run only with streamable HTTP transport.
Recommended defaults:
- `HOST=0.0.0.0`
- `PORT=8000`
- `MCP_HTTP_PATH=/mcp`
- default transport set to `streamable-http`

The `main()` entrypoint should call FastMCP with HTTP transport only.

---

## Files to modify

- `server.py` — extend root FastMCP server with Port and Vessel Info tools; make HTTP-only
- `README.md` — update overview, available tools, transport mode, Docker usage, and Hermes/client configuration
- `Dockerfile` — keep container simple for HTTP runtime
- `requirements.txt` — keep only needed deps

## Implementation details

### `server.py`
Add base URLs for:
- `movements`
- `positions`
- `particulars`
- `srscor`

Add small validators such as:
- `validate_alnum(value, field_name, min_len, max_len)`
- `validate_text_pattern(value, field_name, min_len, max_len, pattern)`

Or one general helper like:
- `validate_string(value, field_name, pattern, min_length, max_length)`

New MCP tools to add:
- `get_vessel_movements_by_imo`
- `get_vessel_positions_snapshot`
- `get_vessel_positions_by_imo`
- `get_vessel_particulars_by_name_pattern`
- `get_vessel_particulars_by_imo`
- `get_srs_certificate_by_certificate_number`
- `get_srs_certificate_by_vessel_details`

Each tool must:
- include a clear description from the OpenAPI spec
- validate its path/query inputs before making requests
- accept `apikey: str`
- forward `apikey` as header `apikey`
- return the same structured JSON shape as existing tools

### `README.md`
Update to describe the root server as covering:
- Schedule
- Port
- Vessel Info

Add the newly available tools.
Document that the server is HTTP streamable only and no longer runs in stdio mode.
Update example commands accordingly.

### `Dockerfile`
Keep the image simple:
- install deps
- copy root files
- expose `8000`
- run `python server.py`

---

## Quality bar

Before calling the work complete, verify:
1. all Port and Vessel Info operations listed above exist as MCP tools;
2. the server description mentions Schedule, Port, and Vessel Info;
3. all new tools accept `apikey` and forward it as header `apikey`;
4. validation exists for new path/query parameters;
5. stdio mode is removed and HTTP streamable transport is the only runtime path;
6. README matches the actual implementation;
7. code remains simple, explicit, and easy to extend later.
