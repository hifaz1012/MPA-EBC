#!/usr/bin/env python3
"""
Minimal MCP client for the local MPA Oceans-X MCP server.

Connects over streamable HTTP to http://localhost:8000/mcp, lists the
available tools, and invokes one with the user-supplied apikey forwarded
as an HTTP header.

Usage (PowerShell):
    # 1. copy .env.example to .env and fill in MPA_APIKEY
    # 2. run:
    .\test_env\Scripts\python.exe client.py

Env vars (loaded from .env in the script directory):
    MPA_APIKEY  required
    MCP_URL     default http://localhost:8000/mcp
    IMO         default 9378785
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# Load .env sitting next to this file (does not override existing env vars).
load_dotenv(Path(__file__).with_name(".env"))

MCP_URL = os.getenv("MCP_URL", "http://localhost:8000/mcp")
NAME = "BINTANG"


async def main() -> int:
    apikey = os.getenv("MPA_APIKEY")
    if not apikey:
        print(
            "ERROR: MPA_APIKEY not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        return 1

    transport = StreamableHttpTransport(
        url=MCP_URL,
        headers={"apikey": apikey},
    )

    async with Client(transport) as client:
        # 1. List available tools
        tools = await client.list_tools()
        print(f"Connected to {MCP_URL}")
        print(f"Available tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t.name}")

        # 2. Call one tool
        tool_name = "get_vessel_particulars_by_name_pattern"
        print(f"\nCalling {tool_name}(charset={NAME!r}) ...")
        result = await client.call_tool(tool_name, {"charset": NAME})

        # 3. Print result
        if result.is_error:
            print("Tool returned an error:")
        for block in result.content:
            text = getattr(block, "text", None)
            if text is None:
                print(block)
                continue
            try:
                print(json.dumps(json.loads(text), indent=2))
            except (ValueError, TypeError):
                print(text)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
