"""Full end-to-end deploy test against the running container."""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


URL = "http://localhost:8765/mcp"


async def main() -> int:
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("apic_deploy_product", {})
            payload = json.loads(res.content[0].text)
            print(json.dumps(payload, indent=2))
            return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
