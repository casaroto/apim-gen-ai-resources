"""MCP server entrypoint that combines the auto-generated Apigee tools with our
custom multipart-upload tools.

Importing `main` triggers the upstream MCPProxy to register every Apigee
operation as a tool. We then read the same env-var configuration the upstream
script uses, fetch the FastMCP instance, register our extra tools, and run.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from autogen.mcp.mcp_proxy.security import BaseSecurity  # noqa: E402

import main  # noqa: E402  -- registers operations on main.app via @app.get/post decorators
import extra_tools  # noqa: E402

app = main.app

if "CONFIG_PATH" in os.environ:
    app.load_configuration(os.environ["CONFIG_PATH"])
if "CONFIG" in os.environ:
    app.load_configuration_from_string(os.environ["CONFIG"])
if "SECURITY" in os.environ:
    security_params = BaseSecurity.parse_security_parameters_from_env(os.environ)
    app.set_security_params(security_params)

mcp_settings = json.loads(os.environ.get("MCP_SETTINGS", "{}"))
mcp = app.get_mcp(**mcp_settings)

extra_tools.register(mcp)

mcp.run(transport="streamable-http")
