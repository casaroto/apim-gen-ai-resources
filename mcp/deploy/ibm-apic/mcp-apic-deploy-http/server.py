"""MCP server (HTTP / streamable-http transport) for IBM API Connect deploy.

Same tools as the stdio server, exposed over HTTP at /mcp.
Designed to run inside a container that bundles the apic Linux CLI and
all working files (credentials.json, product YAMLs).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

logging.basicConfig(
    stream=sys.stderr,
    level=os.environ.get("APIC_MCP_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("apic-mcp-http")

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.properties"
SUBPROCESS_TIMEOUT_SEC = 120


@dataclass
class Config:
    apic_binary_path: str = "/opt/apic/apic"
    working_dir: str = "/opt/apic"
    credentials_file: str = "credentials.json"
    server: str = ""
    username: str = ""
    password: str = ""
    realm: str = ""
    catalog_url: str = ""
    catalog_name: str = ""
    default_product_file: str = ""
    insecure_skip_tls_verify: str = "false"

    @classmethod
    def load(cls, path: Path) -> "Config":
        cfg = cls()
        if not path.exists():
            log.warning("Config file not found at %s; using empty defaults", path)
            return cfg
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg


def _redact(argv: list[str]) -> str:
    out: list[str] = []
    skip_next = False
    for token in argv:
        if skip_next:
            out.append("***")
            skip_next = False
            continue
        if token == "--password":
            out.append(token)
            skip_next = True
            continue
        out.append(token)
    return " ".join(out)


def _maybe_insecure(cfg: "Config", argv: list[str]) -> list[str]:
    if str(cfg.insecure_skip_tls_verify).lower() in ("true", "1", "yes"):
        return [argv[0], "--insecure-skip-tls-verify", *argv[1:]]
    return argv


def run_apic(argv: list[str], working_dir: str) -> dict[str, Any]:
    cmd_str = _redact(argv)
    log.info("running: %s (cwd=%s)", cmd_str, working_dir)
    try:
        proc = subprocess.run(
            argv,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "command": cmd_str,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": e.stdout or "",
            "stderr": f"timeout after {SUBPROCESS_TIMEOUT_SEC}s: {e}",
            "command": cmd_str,
        }
    except FileNotFoundError as e:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"binary not found: {e}",
            "command": cmd_str,
        }


def _require(value: str, name: str) -> str:
    if not value:
        raise ValueError(
            f"missing required value '{name}' (pass as argument or set in config.properties)"
        )
    return value


def tool_set_credentials(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    creds = args.get("credentials_file") or cfg.credentials_file
    creds = _require(creds, "credentials_file")
    return run_apic(
        _maybe_insecure(cfg, [cfg.apic_binary_path, "client-creds:set", creds]),
        cfg.working_dir,
    )


def tool_login(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    server = _require(args.get("server") or cfg.server, "server")
    username = _require(args.get("username") or cfg.username, "username")
    password = _require(args.get("password") or cfg.password, "password")
    realm = _require(args.get("realm") or cfg.realm, "realm")
    return run_apic(
        _maybe_insecure(cfg, [
            cfg.apic_binary_path, "login",
            "--server", server,
            "--username", username,
            "--password", password,
            "--realm", realm,
        ]),
        cfg.working_dir,
    )


def tool_set_catalog(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    url = _require(args.get("catalog_url") or cfg.catalog_url, "catalog_url")
    return run_apic(
        _maybe_insecure(cfg, [cfg.apic_binary_path, "config:set", f"catalog={url}"]),
        cfg.working_dir,
    )


def tool_publish_product(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    product_file = _require(
        args.get("product_file") or cfg.default_product_file, "product_file"
    )
    catalog_name = _require(
        args.get("catalog_name") or cfg.catalog_name, "catalog_name"
    )
    scope = args.get("scope") or "catalog"
    return run_apic(
        _maybe_insecure(cfg, [
            cfg.apic_binary_path, "products:publish", product_file,
            "--scope", scope,
            "--catalog", catalog_name,
        ]),
        cfg.working_dir,
    )


def tool_deploy_product(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    steps: list[tuple[str, dict[str, Any]]] = []
    for name, fn in (
        ("set_credentials", tool_set_credentials),
        ("login", tool_login),
        ("set_catalog", tool_set_catalog),
        ("publish_product", tool_publish_product),
    ):
        result = fn(cfg, args)
        steps.append((name, result))
        if not result["ok"]:
            return {
                "ok": False,
                "failed_step": name,
                "steps": [{"step": s, **r} for s, r in steps],
            }
    return {
        "ok": True,
        "steps": [{"step": s, **r} for s, r in steps],
    }


TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="apic_set_credentials",
        description="Set API Connect client credentials from a JSON file (apic client-creds:set).",
        inputSchema={
            "type": "object",
            "properties": {
                "credentials_file": {"type": "string"},
            },
        },
    ),
    Tool(
        name="apic_login",
        description="Log in to API Connect (apic login). Any omitted argument falls back to config.properties.",
        inputSchema={
            "type": "object",
            "properties": {
                "server": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "realm": {"type": "string"},
            },
        },
    ),
    Tool(
        name="apic_set_catalog",
        description="Set the active catalog URL (apic config:set catalog=<url>).",
        inputSchema={
            "type": "object",
            "properties": {"catalog_url": {"type": "string"}},
        },
    ),
    Tool(
        name="apic_publish_product",
        description="Publish an API product to a catalog (apic products:publish).",
        inputSchema={
            "type": "object",
            "properties": {
                "product_file": {"type": "string"},
                "catalog_name": {"type": "string"},
                "scope": {"type": "string", "default": "catalog"},
            },
        },
    ),
    Tool(
        name="apic_deploy_product",
        description="Run the full deploy flow: set-credentials, login, set-catalog, publish-product. Stops on first failure.",
        inputSchema={
            "type": "object",
            "properties": {
                "credentials_file": {"type": "string"},
                "server": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "realm": {"type": "string"},
                "catalog_url": {"type": "string"},
                "catalog_name": {"type": "string"},
                "product_file": {"type": "string"},
                "scope": {"type": "string", "default": "catalog"},
            },
        },
    ),
]

TOOL_DISPATCH = {
    "apic_set_credentials": tool_set_credentials,
    "apic_login": tool_login,
    "apic_set_catalog": tool_set_catalog,
    "apic_publish_product": tool_publish_product,
    "apic_deploy_product": tool_deploy_product,
}


def build_mcp_server(cfg: Config) -> Server:
    server = Server("apic-deploy-http")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        fn = TOOL_DISPATCH.get(name)
        if fn is None:
            return [TextContent(type="text", text=f"unknown tool: {name}")]
        try:
            result = fn(cfg, arguments or {})
        except ValueError as e:
            result = {"ok": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


def build_app() -> Starlette:
    config_path = Path(os.environ.get("APIC_MCP_CONFIG", DEFAULT_CONFIG_PATH))
    cfg = Config.load(config_path)
    log.info("loaded config from %s (working_dir=%s)", config_path, cfg.working_dir)
    mcp = build_mcp_server(cfg)

    session_mgr = StreamableHTTPSessionManager(app=mcp, json_response=True, stateless=True)

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_mgr.handle_request(scope, receive, send)

    async def healthz(_request):
        return JSONResponse({"ok": True, "service": "apic-deploy-http"})

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        async with session_mgr.run():
            yield

    return Starlette(
        debug=False,
        routes=[
            Route("/healthz", healthz),
            Mount("/mcp", app=handle_mcp),
        ],
        lifespan=lifespan,
    )


app = build_app()


def main() -> None:
    host = os.environ.get("APIC_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("APIC_MCP_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
