"""End-to-end smoke test against the running HTTP MCP server.

Performs initialize -> tools/list -> tools/call (apic_set_credentials),
asserts the 5 tools are exposed and a tool call returns the expected JSON shape.
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


URL = "http://localhost:8765/mcp"


async def main() -> int:
    async with streamablehttp_client(URL) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            expected = sorted([
                "apic_set_credentials",
                "apic_login",
                "apic_set_catalog",
                "apic_publish_product",
                "apic_deploy_product",
            ])
            assert names == expected, f"tools mismatch: {names}"
            print("tools:", names)

            # call apic_set_credentials with no args -> should pull from config
            res = await session.call_tool("apic_set_credentials", {})
            payload = json.loads(res.content[0].text)
            assert "ok" in payload and "command" in payload, payload
            print("set_credentials ok=", payload["ok"], "exit=", payload.get("exit_code"))
            print("stdout head:", (payload.get("stdout") or "")[:200])
            if not payload["ok"]:
                print("stderr:", payload.get("stderr"))
            return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
