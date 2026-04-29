# MPA-EBC

Small Python projects for experimenting with MPA-related APIs and geospatial data workflows.

> This repository is for self-development, prototyping, and learning only. It is not an official MPA project, not production-ready, and not intended as a maintained public product.

## Projects

### `MCP-Server/`
A FastMCP server that exposes selected MPA Oceans-X vessel-related APIs as MCP tools over HTTP.

- Python-based
- `/mcp` endpoint for MCP clients
- `/health` endpoint for container health checks
- For API integration and MCP experimentation

### `Geospatial/`
A CLI utility for converting vector geospatial datasets into GeoJSON and optionally PMTiles.

- Supports zip files, folders, shapefiles, GeoJSON, and other vector inputs
- Useful for repeatable geospatial conversion workflows
- Built for learning and personal tooling

## Quick start

```bash
cd MCP-Server
pip install -r requirements.txt
python server.py
```

```bash
cd Geospatial
pip install -r requirements.txt
python geo_converter.py --help
```

## Repository scope

This repo is a sandbox for trying ideas, building internal practice tools, and learning by implementation. Expect rough edges, incomplete coverage, and breaking changes.