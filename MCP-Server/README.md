# MPA Oceans-X MCP Server

Python FastMCP server for exposing selected MPA Oceans-X vessel-related APIs as MCP tools.

> This project is for self-development, prototyping, and learning only. It is not an official MPA project and is not intended for production use.

## What it includes

The server groups tools around:

- vessel schedule
- port movements and positions
- port clearance records
- vessel information

It runs as an HTTP MCP service and is suitable for local testing, container experiments, and MCP client integration work.

## Requirements

- Python 3.11+
- `fastmcp`
- `httpx`
- `pydantic`

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run locally

```bash
python server.py
```

Default endpoints:

- MCP: `http://localhost:8000/mcp`
- Health: `http://localhost:8000/health`

## Authentication

Clients must send an `apikey` HTTP header to the MCP server. The server forwards that header to the upstream MPA Oceans-X API.

## Docker

```bash
docker build -t mpa-ocx-mcp .
docker run --rm -p 8000:8000 mpa-ocx-mcp
```

## Notes

- The server is designed for experimentation and integration learning.
- Input validation and response shaping are implemented in `server.py`.
- API behaviour depends on the upstream MPA Oceans-X services and a valid API key.