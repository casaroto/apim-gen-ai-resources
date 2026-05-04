"""WSO2 API Manager 4.x REST client.

Wraps the publisher (v4), devportal (v3), client-registration (v0.17), and oauth2 endpoints.
All HTTPS calls disable cert verification because the local APIM uses a self-signed cert.
"""
from __future__ import annotations

import base64
import json
import os
import warnings
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

DEFAULT_BASE = os.environ.get("WSO2_BASE_URL", "https://localhost:9443")
DEFAULT_GW = os.environ.get("WSO2_GW_URL", "https://localhost:8243")

PUBLISHER_SCOPES = " ".join([
    "apim:api_create",
    "apim:api_view",
    "apim:api_publish",
    "apim:api_delete",
    "apim:api_manage",
    "apim:api_import_export",
    "apim:subscribe",
    "apim:app_manage",
    "apim:sub_manage",
])


@dataclass
class WSO2Session:
    base_url: str = DEFAULT_BASE
    gw_url: str = DEFAULT_GW
    username: str = "admin"
    password: str = "admin"
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def auth_header(self) -> dict[str, str]:
        if not self.access_token:
            raise RuntimeError("not logged in: call login() first")
        return {"Authorization": f"Bearer {self.access_token}"}


class WSO2Error(Exception):
    def __init__(self, status: int, body: Any, hint: str | None = None):
        self.status = status
        self.body = body
        self.hint = hint
        super().__init__(f"WSO2 API error {status}: {body} (hint={hint})")


def _check(resp: requests.Response) -> Any:
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise WSO2Error(resp.status_code, body)
    if not resp.content:
        return None
    try:
        return resp.json()
    except Exception:
        return resp.text


def login(session: WSO2Session) -> WSO2Session:
    """Dynamic Client Registration + password grant -> populates session.access_token."""
    if not session.client_id:
        basic = base64.b64encode(f"{session.username}:{session.password}".encode()).decode()
        resp = requests.post(
            urljoin(session.base_url, "/client-registration/v0.17/register"),
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/json",
            },
            json={
                "callbackUrl": "www.example.com",
                "clientName": "mcp_wso2_deploy",
                "owner": session.username,
                "grantType": "password refresh_token client_credentials",
                "saasApp": True,
            },
            verify=False,
            timeout=30,
        )
        body = _check(resp)
        session.client_id = body["clientId"]
        session.client_secret = body["clientSecret"]

    basic = base64.b64encode(f"{session.client_id}:{session.client_secret}".encode()).decode()
    resp = requests.post(
        urljoin(session.base_url, "/oauth2/token"),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "password",
            "username": session.username,
            "password": session.password,
            "scope": PUBLISHER_SCOPES,
        },
        verify=False,
        timeout=30,
    )
    body = _check(resp)
    session.access_token = body["access_token"]
    return session


def list_apis(session: WSO2Session, query: str | None = None) -> list[dict[str, Any]]:
    params = {"limit": 200}
    if query:
        params["query"] = query
    resp = requests.get(
        urljoin(session.base_url, "/api/am/publisher/v4/apis"),
        headers=session.auth_header(),
        params=params,
        verify=False,
        timeout=30,
    )
    body = _check(resp)
    return body.get("list", [])


def find_api(session: WSO2Session, name: str, version: str) -> dict[str, Any] | None:
    for api in list_apis(session, query=f"name:{name}"):
        if api.get("name") == name and api.get("version") == version:
            return api
    return None


def delete_api(session: WSO2Session, api_id: str) -> None:
    # Undeploy any active revisions first
    try:
        deployments = _check(requests.get(
            urljoin(session.base_url, f"/api/am/publisher/v4/apis/{api_id}/deployments"),
            headers=session.auth_header(),
            verify=False,
            timeout=30,
        )) or []
        revs_to_undeploy: dict[str, list[dict]] = {}
        for d in deployments:
            rev_id = d.get("revisionUuid") or d.get("revisionId")
            if rev_id:
                revs_to_undeploy.setdefault(rev_id, []).append({
                    "name": d.get("name", "Default"),
                    "vhost": d.get("vhost", "localhost"),
                    "displayOnDevportal": d.get("displayOnDevportal", True),
                })
        for rev_id, envs in revs_to_undeploy.items():
            requests.post(
                urljoin(session.base_url, f"/api/am/publisher/v4/apis/{api_id}/undeploy-revision"),
                headers={**session.auth_header(), "Content-Type": "application/json"},
                params={"revisionId": rev_id},
                data=json.dumps(envs),
                verify=False,
                timeout=30,
            )
    except WSO2Error:
        pass

    resp = requests.delete(
        urljoin(session.base_url, f"/api/am/publisher/v4/apis/{api_id}"),
        headers=session.auth_header(),
        verify=False,
        timeout=30,
    )
    _check(resp)


def import_openapi(
    session: WSO2Session,
    *,
    name: str,
    version: str,
    context: str,
    openapi_path: str,
    target_endpoint: str,
    gateway_envs: list[str] | None = None,
) -> dict[str, Any]:
    additional = {
        "name": name,
        "version": version,
        "context": context,
        "policies": ["Unlimited"],
        "endpointConfig": {
            "endpoint_type": "http",
            "sandbox_endpoints": {"url": target_endpoint},
            "production_endpoints": {"url": target_endpoint},
        },
        "gatewayVendor": "wso2",
        "gatewayType": "wso2/synapse",
    }
    with open(openapi_path, "rb") as f:
        files = {
            "file": (os.path.basename(openapi_path), f, "application/yaml"),
            "additionalProperties": (None, json.dumps(additional), "application/json"),
        }
        resp = requests.post(
            urljoin(session.base_url, "/api/am/publisher/v4/apis/import-openapi"),
            headers=session.auth_header(),
            files=files,
            verify=False,
            timeout=60,
        )
    return _check(resp)


def deploy_revision(
    session: WSO2Session,
    api_id: str,
    *,
    gateway_env: str = "Default",
    description: str = "auto",
) -> dict[str, Any]:
    rev_resp = requests.post(
        urljoin(session.base_url, f"/api/am/publisher/v4/apis/{api_id}/revisions"),
        headers={**session.auth_header(), "Content-Type": "application/json"},
        json={"description": description},
        verify=False,
        timeout=60,
    )
    rev = _check(rev_resp)
    revision_id = rev["id"]

    deploy_resp = requests.post(
        urljoin(session.base_url, f"/api/am/publisher/v4/apis/{api_id}/deploy-revision"),
        headers={**session.auth_header(), "Content-Type": "application/json"},
        params={"revisionId": revision_id},
        json=[{
            "name": gateway_env,
            "vhost": "localhost",
            "displayOnDevportal": True,
        }],
        verify=False,
        timeout=60,
    )
    _check(deploy_resp)
    return {"revision_id": revision_id, "gateway_env": gateway_env}


def publish_api(session: WSO2Session, api_id: str) -> dict[str, Any]:
    resp = requests.post(
        urljoin(session.base_url, "/api/am/publisher/v4/apis/change-lifecycle"),
        headers=session.auth_header(),
        params={"action": "Publish", "apiId": api_id},
        verify=False,
        timeout=30,
    )
    return _check(resp)


def get_devportal_token(session: WSO2Session) -> str:
    """DevPortal needs its own token with devportal scopes."""
    devportal_scopes = " ".join([
        "apim:subscribe",
        "apim:app_manage",
        "apim:sub_manage",
        "apim:app_import_export",
    ])
    basic = base64.b64encode(f"{session.client_id}:{session.client_secret}".encode()).decode()
    resp = requests.post(
        urljoin(session.base_url, "/oauth2/token"),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "password",
            "username": session.username,
            "password": session.password,
            "scope": devportal_scopes,
        },
        verify=False,
        timeout=30,
    )
    body = _check(resp)
    return body["access_token"]


def create_subscription(
    session: WSO2Session,
    api_id: str,
    *,
    app_name: str = "default-app",
    tier: str = "Unlimited",
) -> dict[str, Any]:
    dp_token = get_devportal_token(session)
    headers = {"Authorization": f"Bearer {dp_token}", "Content-Type": "application/json"}

    # Create app (idempotent-ish: 409 if exists, then look up)
    app_id = None
    resp = requests.post(
        urljoin(session.base_url, "/api/am/devportal/v3/applications"),
        headers=headers,
        json={
            "name": app_name,
            "throttlingPolicy": tier,
            "description": "auto-created by mcp",
            "tokenType": "JWT",
        },
        verify=False,
        timeout=30,
    )
    if resp.status_code == 409:
        list_resp = requests.get(
            urljoin(session.base_url, "/api/am/devportal/v3/applications"),
            headers=headers,
            params={"query": app_name},
            verify=False,
            timeout=30,
        )
        for app in _check(list_resp).get("list", []):
            if app["name"] == app_name:
                app_id = app["applicationId"]
                break
    else:
        app_body = _check(resp)
        app_id = app_body["applicationId"]

    if not app_id:
        raise WSO2Error(0, "could not create or find application", hint=app_name)

    # Subscribe
    sub_resp = requests.post(
        urljoin(session.base_url, "/api/am/devportal/v3/subscriptions"),
        headers=headers,
        json={"applicationId": app_id, "apiId": api_id, "throttlingPolicy": tier},
        verify=False,
        timeout=30,
    )
    sub_body = _check(sub_resp) if sub_resp.status_code != 409 else {"subscriptionId": None}

    # Generate keys
    keys_resp = requests.post(
        urljoin(session.base_url, f"/api/am/devportal/v3/applications/{app_id}/generate-keys"),
        headers=headers,
        json={
            "keyType": "PRODUCTION",
            "grantTypesToBeSupported": ["client_credentials", "password"],
            "callbackUrl": "",
            "scopes": ["am_application_scope", "default"],
            "validityTime": 3600,
            "additionalProperties": {},
        },
        verify=False,
        timeout=30,
    )
    if keys_resp.status_code == 409:
        # Keys already generated — fetch existing
        existing = _check(requests.get(
            urljoin(session.base_url, f"/api/am/devportal/v3/applications/{app_id}/keys"),
            headers=headers,
            verify=False,
            timeout=30,
        ))
        prod = next((k for k in existing.get("list", []) if k.get("keyType") == "PRODUCTION"), None)
        if not prod:
            raise WSO2Error(409, "keys exist but PRODUCTION not found")
        keys = prod
    else:
        keys = _check(keys_resp)

    return {
        "application_id": app_id,
        "subscription_id": sub_body.get("subscriptionId"),
        "consumer_key": keys["consumerKey"],
        "consumer_secret": keys["consumerSecret"],
    }


def get_access_token(consumer_key: str, consumer_secret: str, *, base_url: str = DEFAULT_BASE, scope: str = "default") -> dict[str, Any]:
    basic = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
    resp = requests.post(
        urljoin(base_url, "/oauth2/token"),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials", "scope": scope},
        verify=False,
        timeout=30,
    )
    return _check(resp)


def invoke_api(
    session: WSO2Session,
    api_id: str | None = None,
    *,
    gateway_url: str | None = None,
    path: str = "/",
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
    access_token: str,
) -> dict[str, Any]:
    if not gateway_url:
        if not api_id:
            raise ValueError("either api_id or gateway_url must be given")
        info = _check(requests.get(
            urljoin(session.base_url, f"/api/am/publisher/v4/apis/{api_id}"),
            headers=session.auth_header(),
            verify=False,
            timeout=30,
        ))
        ctx = info["context"]
        ver = info["version"]
        if not ctx.endswith("/" + ver):
            base_path = f"{ctx}/{ver}"
        else:
            base_path = ctx
        gateway_url = f"{session.gw_url}{base_path}"

    url = gateway_url.rstrip("/") + "/" + path.lstrip("/")
    h = {"Authorization": f"Bearer {access_token}"}
    if headers:
        h.update(headers)
    if body is not None and "Content-Type" not in h:
        h["Content-Type"] = "application/json"

    resp = requests.request(
        method.upper(),
        url,
        headers=h,
        json=body if body is not None else None,
        verify=False,
        timeout=30,
    )
    try:
        parsed = resp.json()
    except Exception:
        parsed = resp.text
    return {"status": resp.status_code, "url": url, "body": parsed}
