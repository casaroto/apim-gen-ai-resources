"""MCP server exposing WSO2 deploy tools over streamable-http transport."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import wso2_client as wc

mcp = FastMCP("wso2-deploy", host="0.0.0.0", port=int(os.environ.get("WSO2_MCP_PORT", "8767")))

_session = wc.WSO2Session(
    base_url=os.environ.get("WSO2_BASE_URL", wc.DEFAULT_BASE),
    gw_url=os.environ.get("WSO2_GW_URL", wc.DEFAULT_GW),
    username=os.environ.get("WSO2_USERNAME", "admin"),
    password=os.environ.get("WSO2_PASSWORD", "admin"),
)


def _ensure_login() -> None:
    if not _session.access_token:
        wc.login(_session)


@mcp.tool()
def wso2_login(username: str = "admin", password: str = "admin", base_url: str | None = None) -> dict[str, Any]:
    """DCR + OAuth2 password grant. Caches token in process memory."""
    _session.username = username
    _session.password = password
    if base_url:
        _session.base_url = base_url
    _session.client_id = None
    _session.access_token = None
    wc.login(_session)
    return {"logged_in": True, "client_id": _session.client_id}


@mcp.tool()
def wso2_import_openapi(
    name: str,
    version: str,
    context: str,
    openapi_path: str,
    target_endpoint: str,
) -> dict[str, Any]:
    """Create a WSO2 API from a local OpenAPI file. Returns api_id."""
    _ensure_login()
    api = wc.import_openapi(
        _session, name=name, version=version, context=context,
        openapi_path=openapi_path, target_endpoint=target_endpoint,
    )
    return {"api_id": api["id"], "name": api["name"], "version": api["version"], "context": api["context"]}


@mcp.tool()
def wso2_import_openapi_file(
    name: str,
    version: str,
    context: str,
    openapi_file: str,
    target_endpoint: str,
    file_name: str = "openapi.yaml",
) -> dict[str, Any]:
    """Create a WSO2 API from OpenAPI YAML/JSON content supplied directly."""
    if not openapi_file.strip():
        raise ValueError("openapi_file must contain OpenAPI YAML or JSON content.")
    suffix = Path(file_name).suffix or ".yaml"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            prefix="wso2-openapi-",
            encoding="utf-8",
            delete=False,
        ) as temp_file:
            temp_file.write(openapi_file)
            temp_path = Path(temp_file.name)

        return wso2_import_openapi(
            name=name,
            version=version,
            context=context,
            openapi_path=str(temp_path),
            target_endpoint=target_endpoint,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@mcp.tool()
def wso2_deploy_revision(api_id: str, gateway_env: str = "Default") -> dict[str, Any]:
    """Create a revision and deploy it to the named gateway env."""
    _ensure_login()
    return wc.deploy_revision(_session, api_id, gateway_env=gateway_env)


@mcp.tool()
def wso2_publish_api(api_id: str) -> dict[str, Any]:
    """Lifecycle transition CREATED -> PUBLISHED."""
    _ensure_login()
    return wc.publish_api(_session, api_id)


@mcp.tool()
def wso2_create_subscription(api_id: str, app_name: str = "default-app", tier: str = "Unlimited") -> dict[str, Any]:
    """Create app, subscribe, generate PRODUCTION keys."""
    _ensure_login()
    return wc.create_subscription(_session, api_id, app_name=app_name, tier=tier)


@mcp.tool()
def wso2_get_access_token(consumer_key: str, consumer_secret: str, scope: str = "default") -> dict[str, Any]:
    """OAuth2 client_credentials token for invoking the API through the gateway."""
    return wc.get_access_token(consumer_key, consumer_secret, base_url=_session.base_url, scope=scope)


@mcp.tool()
def wso2_invoke_api(
    api_id: str,
    path: str = "/",
    method: str = "GET",
    body: Any = None,
    access_token: str = "",
) -> dict[str, Any]:
    """Invoke the deployed API through the WSO2 gateway."""
    _ensure_login()
    return wc.invoke_api(_session, api_id=api_id, path=path, method=method, body=body, access_token=access_token)


@mcp.tool()
def wso2_list_apis(query: str | None = None) -> list[dict[str, Any]]:
    """List APIs in the publisher (optionally filtered by query, e.g. 'name:BooksAPI')."""
    _ensure_login()
    return wc.list_apis(_session, query=query)


@mcp.tool()
def wso2_delete_api(api_id: str) -> dict[str, Any]:
    """Undeploy revisions and hard-delete the API."""
    _ensure_login()
    wc.delete_api(_session, api_id)
    return {"deleted": True, "api_id": api_id}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
