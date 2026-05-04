"""MCP server (HTTP / streamable-http transport) for Kong API Gateway.

Talks to Kong's Admin API to upsert Services and Routes, and to deploy an
OpenAPI spec as a Service+Route pair in one shot.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import uvicorn
import yaml
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

logging.basicConfig(
    stream=sys.stderr,
    level=os.environ.get("KONG_MCP_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("kong-mcp-http")

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.properties"


@dataclass
class Config:
    admin_url: str = "http://host.containers.internal:8001"
    admin_token: str = ""
    request_timeout: float = 30.0
    working_dir: str = "/opt/kong"
    default_service_name: str = ""
    default_upstream_url: str = ""
    default_route_path: str = ""

    @classmethod
    def load(cls, path: Path) -> "Config":
        cfg = cls()
        if not path.exists():
            log.warning("Config file not found at %s; using defaults", path)
            return cfg
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not hasattr(cfg, key):
                continue
            if isinstance(getattr(cfg, key), float):
                value = float(value)
            setattr(cfg, key, value)
        # Env override for admin URL is convenient for local runs.
        cfg.admin_url = os.environ.get("KONG_ADMIN_URL", cfg.admin_url)
        cfg.admin_token = os.environ.get("KONG_ADMIN_TOKEN", cfg.admin_token)
        return cfg


def _require(value: Any, name: str) -> Any:
    if value in (None, "", []):
        raise ValueError(f"missing required value '{name}'")
    return value


def _admin_request(cfg: Config, method: str, path: str, json_body: Any = None) -> dict[str, Any]:
    headers = {"Kong-Admin-Token": cfg.admin_token} if cfg.admin_token else {}
    log.info("kong-admin %s %s%s", method, cfg.admin_url, path)
    try:
        with httpx.Client(base_url=cfg.admin_url, timeout=cfg.request_timeout, headers=headers) as c:
            r = c.request(method, path, json=json_body)
        try:
            body: Any = r.json()
        except ValueError:
            body = r.text
        return {
            "ok": r.is_success,
            "status_code": r.status_code,
            "method": method,
            "path": path,
            "body": body,
        }
    except httpx.HTTPError as e:
        return {
            "ok": False,
            "status_code": -1,
            "method": method,
            "path": path,
            "error": str(e),
        }


def _parse_upstream(url: str) -> dict[str, Any]:
    p = urlparse(url)
    if not p.scheme or not p.hostname:
        raise ValueError(f"invalid upstream url: {url}")
    port = p.port or (443 if p.scheme == "https" else 80)
    out: dict[str, Any] = {"protocol": p.scheme, "host": p.hostname, "port": port}
    if p.path and p.path != "/":
        out["path"] = p.path
    return out


def _slugify(s: str) -> str:
    chars = []
    for c in (s or "").lower():
        if c.isalnum():
            chars.append(c)
        elif c in (" ", "_", "-", "."):
            chars.append("-")
    out = "".join(chars).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "service"


def tool_get_status(cfg: Config, _args: dict[str, Any]) -> dict[str, Any]:
    return _admin_request(cfg, "GET", "/status")


def tool_list_services(cfg: Config, _args: dict[str, Any]) -> dict[str, Any]:
    return _admin_request(cfg, "GET", "/services")


def tool_list_routes(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    svc = args.get("service")
    return _admin_request(cfg, "GET", f"/services/{svc}/routes" if svc else "/routes")


def tool_apply_service(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    name = _require(args.get("name") or cfg.default_service_name, "name")
    upstream_url = _require(args.get("upstream_url") or cfg.default_upstream_url, "upstream_url")
    body = {"name": name, **_parse_upstream(upstream_url)}
    return _admin_request(cfg, "PUT", f"/services/{name}", body)


def tool_apply_route(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    name = _require(args.get("name"), "name")
    service = _require(args.get("service") or cfg.default_service_name, "service")
    paths = args.get("paths") or ([cfg.default_route_path] if cfg.default_route_path else None)
    paths = _require(paths, "paths")
    if isinstance(paths, str):
        paths = [paths]
    body: dict[str, Any] = {
        "name": name,
        "paths": paths,
        "strip_path": bool(args.get("strip_path", True)),
    }
    if args.get("methods"):
        body["methods"] = args["methods"]
    if args.get("hosts"):
        body["hosts"] = args["hosts"]
    return _admin_request(cfg, "PUT", f"/services/{service}/routes/{name}", body)


def tool_delete_service(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    name = _require(args.get("name"), "name")
    deleted_routes = []
    routes = _admin_request(cfg, "GET", f"/services/{name}/routes")
    if routes.get("ok"):
        for r in routes["body"].get("data", []):
            res = _admin_request(cfg, "DELETE", f"/routes/{r['id']}")
            deleted_routes.append({"id": r["id"], "status_code": res["status_code"]})
    final = _admin_request(cfg, "DELETE", f"/services/{name}")
    final["deleted_routes"] = deleted_routes
    return final


def _apply_openapi_document(
    cfg: Config,
    args: dict[str, Any],
    spec: dict[str, Any],
    source_name: str,
) -> dict[str, Any]:
    info = spec.get("info") or {}
    title = info.get("title") or "api"
    version = info.get("version") or ""

    service_name = args.get("service_name") or cfg.default_service_name or _slugify(title)
    upstream_url = _require(args.get("upstream_url") or cfg.default_upstream_url, "upstream_url")

    route_path = args.get("route_path") or cfg.default_route_path
    if not route_path:
        servers = spec.get("servers") or []
        if servers:
            sp = urlparse(servers[0].get("url", ""))
            if sp.path and sp.path != "/":
                route_path = sp.path.rstrip("/")
        if not route_path:
            route_path = f"/{_slugify(title)}"

    route_name = args.get("route_name") or f"{service_name}-route"

    steps: list[dict[str, Any]] = []
    svc = tool_apply_service(cfg, {"name": service_name, "upstream_url": upstream_url})
    steps.append({"step": "apply_service", **svc})
    if not svc["ok"]:
        return {"ok": False, "failed_step": "apply_service", "steps": steps}

    rt = tool_apply_route(cfg, {
        "name": route_name,
        "service": service_name,
        "paths": [route_path],
        "strip_path": args.get("strip_path", True),
    })
    steps.append({"step": "apply_route", **rt})
    if not rt["ok"]:
        return {"ok": False, "failed_step": "apply_route", "steps": steps}

    return {
        "ok": True,
        "openapi_title": title,
        "openapi_version": version,
        "service": service_name,
        "route": route_name,
        "route_path": route_path,
        "upstream_url": upstream_url,
        "spec_file": source_name,
        "steps": steps,
    }


def tool_apply_openapi(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    spec_arg = _require(args.get("spec_file"), "spec_file")
    p = Path(spec_arg)
    if not p.is_absolute():
        p = Path(cfg.working_dir) / p
    if not p.exists():
        return {"ok": False, "error": f"spec file not found: {p}"}

    try:
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return {"ok": False, "error": f"invalid YAML in {p}: {e}"}
    if not isinstance(spec, dict):
        return {"ok": False, "error": f"OpenAPI file must contain an object: {p}"}
    return _apply_openapi_document(cfg, args, spec, str(p))


def tool_apply_openapi_file(cfg: Config, args: dict[str, Any]) -> dict[str, Any]:
    openapi_file = _require(args.get("openapi_file") or args.get("spec_file"), "openapi_file")
    file_name = args.get("file_name") or "openapi.yaml"
    try:
        spec = yaml.safe_load(openapi_file)
    except yaml.YAMLError as e:
        return {"ok": False, "error": f"invalid YAML in {file_name}: {e}"}
    if not isinstance(spec, dict):
        return {"ok": False, "error": f"OpenAPI file must contain an object: {file_name}"}
    return _apply_openapi_document(cfg, args, spec, file_name)


TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="kong_get_status",
        description="Get Kong node status (GET /status). Useful as a health/connectivity check.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="kong_list_services",
        description="List all Kong Services (GET /services).",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="kong_list_routes",
        description="List all Kong Routes (GET /routes), or routes for a given service when 'service' is set.",
        inputSchema={
            "type": "object",
            "properties": {"service": {"type": "string"}},
        },
    ),
    Tool(
        name="kong_apply_service",
        description="Upsert a Kong Service by name (PUT /services/{name}). Pass 'upstream_url' like http://backend:3000.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "upstream_url": {"type": "string"},
            },
            "required": ["name", "upstream_url"],
        },
    ),
    Tool(
        name="kong_apply_route",
        description="Upsert a Kong Route by name (PUT /services/{service}/routes/{name}).",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "service": {"type": "string"},
                "paths": {"type": "array", "items": {"type": "string"}},
                "methods": {"type": "array", "items": {"type": "string"}},
                "hosts": {"type": "array", "items": {"type": "string"}},
                "strip_path": {"type": "boolean", "default": True},
            },
            "required": ["name", "service", "paths"],
        },
    ),
    Tool(
        name="kong_delete_service",
        description="Delete a Kong Service and all its routes by name.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    ),
    Tool(
        name="kong_apply_openapi",
        description="Deploy an OpenAPI spec to Kong as a Service+Route. Reads the spec, derives names/paths from info.title and servers[0].url, then upserts.",
        inputSchema={
            "type": "object",
            "properties": {
                "spec_file": {"type": "string", "description": "Path to OpenAPI YAML/JSON inside the container (relative to working_dir)."},
                "upstream_url": {"type": "string", "description": "Where Kong should send traffic (e.g. http://backend:3000)."},
                "service_name": {"type": "string"},
                "route_name": {"type": "string"},
                "route_path": {"type": "string"},
                "strip_path": {"type": "boolean", "default": True},
            },
            "required": ["spec_file"],
        },
    ),
    Tool(
        name="kong_apply_openapi_file",
        description="Deploy OpenAPI YAML/JSON content supplied directly to the MCP tool as a Kong Service+Route.",
        inputSchema={
            "type": "object",
            "properties": {
                "openapi_file": {"type": "string", "description": "OpenAPI YAML/JSON content."},
                "spec_file": {"type": "string", "description": "Alias for openapi_file content."},
                "file_name": {"type": "string", "default": "openapi.yaml"},
                "upstream_url": {"type": "string", "description": "Where Kong should send traffic (e.g. http://backend:3000)."},
                "service_name": {"type": "string"},
                "route_name": {"type": "string"},
                "route_path": {"type": "string"},
                "strip_path": {"type": "boolean", "default": True},
            },
            "required": ["openapi_file"],
        },
    ),
]

TOOL_DISPATCH = {
    "kong_get_status": tool_get_status,
    "kong_list_services": tool_list_services,
    "kong_list_routes": tool_list_routes,
    "kong_apply_service": tool_apply_service,
    "kong_apply_route": tool_apply_route,
    "kong_delete_service": tool_delete_service,
    "kong_apply_openapi": tool_apply_openapi,
    "kong_apply_openapi_file": tool_apply_openapi_file,
}


def build_mcp_server(cfg: Config) -> Server:
    server = Server("kong-deploy-http")

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
    config_path = Path(os.environ.get("KONG_MCP_CONFIG", DEFAULT_CONFIG_PATH))
    cfg = Config.load(config_path)
    log.info("kong admin: %s (working_dir=%s)", cfg.admin_url, cfg.working_dir)
    mcp = build_mcp_server(cfg)

    session_mgr = StreamableHTTPSessionManager(app=mcp, json_response=True, stateless=True)

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_mgr.handle_request(scope, receive, send)

    async def healthz(_request):
        return JSONResponse({"ok": True, "service": "kong-deploy-http", "admin": cfg.admin_url})

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
    host = os.environ.get("KONG_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("KONG_MCP_PORT", "8770"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
