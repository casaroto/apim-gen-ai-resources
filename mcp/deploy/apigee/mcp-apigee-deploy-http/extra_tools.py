"""Custom Apigee MCP tools for operations the upstream proxy can't handle.

Auto-generated MCPProxy only sends JSON request bodies, so it can't import an
API proxy ZIP bundle (which is multipart/form-data). These tools call the
Apigee Admin API directly with `requests`, sharing the same BEARER_TOKEN.

Bundle files live under APIGEE_BUNDLE_DIR (default /opt/apigee). Mount your
local directory there at run time:
    podman run -v $PWD/bundles:/opt/apigee:ro,Z -e BEARER_TOKEN=... ...
"""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any

import requests

DEFAULT_BUNDLE_DIR = os.environ.get("APIGEE_BUNDLE_DIR", "/opt/apigee")
APIGEE_BASE = os.environ.get("APIGEE_API_BASE", "https://apigee.googleapis.com")
HTTP_TIMEOUT = float(os.environ.get("APIGEE_HTTP_TIMEOUT", "120"))


def _token() -> str:
    tok = os.environ.get("BEARER_TOKEN", "")
    if not tok:
        raise RuntimeError("BEARER_TOKEN env var is not set")
    return tok


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else Path(DEFAULT_BUNDLE_DIR) / path


def _result(r: requests.Response) -> dict[str, Any]:
    try:
        body: Any = r.json()
    except ValueError:
        body = r.text
    return {"ok": r.ok, "status_code": r.status_code, "body": body}


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


def _decode_bundle(bundle_file_base64: str) -> bytes:
    content = bundle_file_base64.strip()
    if not content:
        raise ValueError("bundle_file_base64 must contain a base64-encoded ZIP bundle.")
    if "," in content and content.split(",", 1)[0].startswith("data:"):
        content = content.split(",", 1)[1]
    return base64.b64decode(content, validate=True)


def register(mcp: Any) -> None:
    @mcp.tool(
        name="apigee_import_proxy_bundle",
        description=(
            "Import an Apigee API proxy ZIP bundle (multipart upload). "
            f"Mount your local bundle dir at {DEFAULT_BUNDLE_DIR} or pass an absolute path. "
            "Returns the new revision number."
        ),
    )
    def apigee_import_proxy_bundle(
        organization: str,
        name: str,
        bundle_file: str,
    ) -> dict[str, Any]:
        path = _resolve(bundle_file)
        if not path.exists():
            return {"ok": False, "error": f"bundle file not found: {path}"}
        url = f"{APIGEE_BASE}/v1/organizations/{organization}/apis"
        with path.open("rb") as f:
            r = requests.post(
                url,
                params={"action": "import", "name": name},
                headers=_auth(),
                files={"file": (path.name, f, "application/zip")},
                timeout=HTTP_TIMEOUT,
            )
        return _result(r)

    @mcp.tool(
        name="apigee_import_proxy_bundle_file",
        description=(
            "Import an Apigee API proxy ZIP bundle from base64 content supplied directly "
            "to the MCP tool. Returns the new revision number."
        ),
    )
    def apigee_import_proxy_bundle_file(
        organization: str,
        name: str,
        bundle_file_base64: str,
        file_name: str = "apiproxy.zip",
    ) -> dict[str, Any]:
        try:
            bundle_bytes = _decode_bundle(bundle_file_base64)
        except Exception as exc:
            return {"ok": False, "error": f"invalid base64 bundle content: {exc}"}

        suffix = Path(file_name).suffix or ".zip"
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            prefix="apigee-bundle-",
            delete=False,
        ) as tmp:
            tmp.write(bundle_bytes)
            temp_path = Path(tmp.name)
        try:
            return apigee_import_proxy_bundle(
                organization=organization,
                name=name,
                bundle_file=str(temp_path),
            )
        finally:
            temp_path.unlink(missing_ok=True)

    @mcp.tool(
        name="apigee_deploy_proxy_revision",
        description="Deploy a proxy revision to an environment (POST .../revisions/{rev}/deployments).",
    )
    def apigee_deploy_proxy_revision(
        organization: str,
        environment: str,
        name: str,
        revision: str,
        override: bool = True,
    ) -> dict[str, Any]:
        url = (
            f"{APIGEE_BASE}/v1/organizations/{organization}/environments/{environment}"
            f"/apis/{name}/revisions/{revision}/deployments"
        )
        r = requests.post(
            url,
            params={"override": str(override).lower()},
            headers=_auth(),
            timeout=HTTP_TIMEOUT,
        )
        return _result(r)

    @mcp.tool(
        name="apigee_undeploy_proxy_revision",
        description="Undeploy a proxy revision from an environment.",
    )
    def apigee_undeploy_proxy_revision(
        organization: str,
        environment: str,
        name: str,
        revision: str,
    ) -> dict[str, Any]:
        url = (
            f"{APIGEE_BASE}/v1/organizations/{organization}/environments/{environment}"
            f"/apis/{name}/revisions/{revision}/deployments"
        )
        r = requests.delete(url, headers=_auth(), timeout=HTTP_TIMEOUT)
        return _result(r)

    @mcp.tool(
        name="apigee_get_proxy_deployment",
        description="Get deployment status of a proxy revision in an environment.",
    )
    def apigee_get_proxy_deployment(
        organization: str,
        environment: str,
        name: str,
        revision: str,
    ) -> dict[str, Any]:
        url = (
            f"{APIGEE_BASE}/v1/organizations/{organization}/environments/{environment}"
            f"/apis/{name}/revisions/{revision}/deployments"
        )
        r = requests.get(url, headers=_auth(), timeout=HTTP_TIMEOUT)
        return _result(r)

    @mcp.tool(
        name="apigee_list_envgroup_hostnames",
        description="List envgroup hostnames for an organization. Use these to call deployed proxies.",
    )
    def apigee_list_envgroup_hostnames(organization: str) -> dict[str, Any]:
        url = f"{APIGEE_BASE}/v1/organizations/{organization}/envgroups"
        r = requests.get(url, headers=_auth(), timeout=HTTP_TIMEOUT)
        res = _result(r)
        if res["ok"] and isinstance(res["body"], dict):
            res["hostnames"] = {
                g["name"]: g.get("hostnames", [])
                for g in res["body"].get("environmentGroups", [])
            }
        return res

    @mcp.tool(
        name="apigee_deploy_proxy_bundle",
        description=(
            "Full deploy flow: import a ZIP bundle and immediately deploy the resulting "
            "revision to the given environment. Stops on first failure."
        ),
    )
    def apigee_deploy_proxy_bundle(
        organization: str,
        environment: str,
        name: str,
        bundle_file: str,
        override: bool = True,
    ) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        imp = apigee_import_proxy_bundle(organization=organization, name=name, bundle_file=bundle_file)
        steps.append({"step": "import_proxy_bundle", **imp})
        if not imp["ok"]:
            return {"ok": False, "failed_step": "import_proxy_bundle", "steps": steps}

        rev = imp["body"].get("revision") if isinstance(imp["body"], dict) else None
        if not rev:
            return {"ok": False, "error": "no revision returned from import", "steps": steps}

        dep = apigee_deploy_proxy_revision(
            organization=organization,
            environment=environment,
            name=name,
            revision=str(rev),
            override=override,
        )
        steps.append({"step": "deploy_proxy_revision", **dep})
        if not dep["ok"]:
            return {"ok": False, "failed_step": "deploy_proxy_revision", "steps": steps}

        return {
            "ok": True,
            "organization": organization,
            "environment": environment,
            "name": name,
            "revision": rev,
            "steps": steps,
        }

    @mcp.tool(
        name="apigee_deploy_proxy_bundle_file",
        description=(
            "Full deploy flow from a base64-encoded ZIP bundle supplied directly: "
            "import the bundle and deploy the resulting revision."
        ),
    )
    def apigee_deploy_proxy_bundle_file(
        organization: str,
        environment: str,
        name: str,
        bundle_file_base64: str,
        file_name: str = "apiproxy.zip",
        override: bool = True,
    ) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        imp = apigee_import_proxy_bundle_file(
            organization=organization,
            name=name,
            bundle_file_base64=bundle_file_base64,
            file_name=file_name,
        )
        steps.append({"step": "import_proxy_bundle_file", **imp})
        if not imp["ok"]:
            return {"ok": False, "failed_step": "import_proxy_bundle_file", "steps": steps}

        rev = imp["body"].get("revision") if isinstance(imp["body"], dict) else None
        if not rev:
            return {"ok": False, "error": "no revision returned from import", "steps": steps}

        dep = apigee_deploy_proxy_revision(
            organization=organization,
            environment=environment,
            name=name,
            revision=str(rev),
            override=override,
        )
        steps.append({"step": "deploy_proxy_revision", **dep})
        if not dep["ok"]:
            return {"ok": False, "failed_step": "deploy_proxy_revision", "steps": steps}

        return {
            "ok": True,
            "organization": organization,
            "environment": environment,
            "name": name,
            "revision": rev,
            "steps": steps,
        }
