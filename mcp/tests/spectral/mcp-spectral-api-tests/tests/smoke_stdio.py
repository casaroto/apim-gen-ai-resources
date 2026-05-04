from __future__ import annotations

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(
        command="docker",
        args=["run", "--rm", "-i", "spectral-api-tests-mcp:latest"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([tool.name for tool in tools.tools])

            version = await session.call_tool("spectral_version", {})
            print(version.content[0].text)

            result = await session.call_tool("spectral_lint_default_branchesmock", {})
            print(result.content[0].text[:1000])

            api_file = Path("assets/branchesmock_1.0.0.yaml").read_text(encoding="utf-8")
            file_result = await session.call_tool(
                "spectral_lint_api_file",
                {"api_file": api_file, "file_name": "branchesmock_1.0.0.yaml"},
            )
            print(file_result.content[0].text[:1000])


if __name__ == "__main__":
    asyncio.run(main())
