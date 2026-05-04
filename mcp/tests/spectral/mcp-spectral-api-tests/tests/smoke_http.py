from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = os.environ.get("SPECTRAL_MCP_HTTP_URL", "http://localhost:8771/mcp")


async def main() -> None:
    async with streamablehttp_client(URL) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            print(names)

            expected = sorted(
                [
                    "spectral_version",
                    "spectral_lint_api",
                    "spectral_lint_api_file",
                    "spectral_lint_default_branchesmock",
                ]
            )
            assert names == expected, f"tools mismatch: {names}"

            version = await session.call_tool("spectral_version", {})
            print(version.content[0].text)

            result = await session.call_tool("spectral_lint_default_branchesmock", {})
            payload = json.loads(result.content[0].text)
            summary = {
                "passed": payload["passed"],
                "returncode": payload["returncode"],
                "api_path": payload["api_path"],
                "ruleset_path": payload["ruleset_path"],
                "finding_count": payload["finding_count"],
                "summary": payload["summary"],
            }
            print(json.dumps(summary, indent=2))

            api_file = Path("assets/branchesmock_1.0.0.yaml").read_text(encoding="utf-8")
            file_result = await session.call_tool(
                "spectral_lint_api_file",
                {"api_file": api_file, "file_name": "branchesmock_1.0.0.yaml"},
            )
            file_payload = json.loads(file_result.content[0].text)
            file_summary = {
                "passed": file_payload["passed"],
                "returncode": file_payload["returncode"],
                "api_file_name": file_payload["api_file_name"],
                "finding_count": file_payload["finding_count"],
                "summary": file_payload["summary"],
            }
            print(json.dumps(file_summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
