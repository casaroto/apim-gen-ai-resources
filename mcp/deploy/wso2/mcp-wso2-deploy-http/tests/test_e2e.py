"""End-to-end deploy of the kong-demo Books API to local WSO2 APIM, exercised through the MCP tool functions.

Runs against a live `wso2am` container at https://localhost:9443 / https://localhost:8243.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import wso2_client as wc  # noqa: E402

OPENAPI = Path("/Users/casaroto/projetos/kong-demo/openapi.yaml")
API_NAME = "BooksAPI"
API_VERSION = "1.0.0"
API_CONTEXT = "/books-api"
TARGET_ENDPOINT = "http://books-backend:3000"


@pytest.fixture(scope="session")
def session():
    s = wc.WSO2Session()
    wc.login(s)
    return s


@pytest.fixture(scope="session", autouse=True)
def cleanup_existing(session):
    """Hard-delete any pre-existing BooksAPI:1.0.0 so the test starts clean."""
    existing = wc.find_api(session, API_NAME, API_VERSION)
    if existing:
        print(f"\n[cleanup] deleting existing API {existing['id']}")
        wc.delete_api(session, existing["id"])


def test_full_deploy_flow(session):
    # 1. Import OpenAPI
    api = wc.import_openapi(
        session,
        name=API_NAME,
        version=API_VERSION,
        context=API_CONTEXT,
        openapi_path=str(OPENAPI),
        target_endpoint=TARGET_ENDPOINT,
    )
    api_id = api["id"]
    print(f"[1] imported api_id={api_id}")
    assert api["name"] == API_NAME
    assert api["version"] == API_VERSION

    # 2. Deploy revision
    rev = wc.deploy_revision(session, api_id)
    print(f"[2] deployed revision={rev}")
    assert rev["revision_id"]

    # 3. Publish
    pub = wc.publish_api(session, api_id)
    print(f"[3] published lifecycle={pub}")

    # 4. Subscribe
    sub = wc.create_subscription(session, api_id, app_name="books-test-app")
    print(f"[4] subscribed app={sub['application_id']}")
    assert sub["consumer_key"]
    assert sub["consumer_secret"]

    # 5. Token
    token = wc.get_access_token(sub["consumer_key"], sub["consumer_secret"])
    print(f"[5] got token len={len(token['access_token'])}")
    assert token["access_token"]

    # 6. Wait briefly for gateway to pick up the deployment, then invoke
    time.sleep(10)

    # /health
    r = wc.invoke_api(session, api_id=api_id, path="/health", access_token=token["access_token"])
    print(f"[6a] /health -> {r['status']} {r['body']}")
    assert r["status"] == 200, r

    # /books
    r = wc.invoke_api(session, api_id=api_id, path="/books", access_token=token["access_token"])
    print(f"[6b] /books -> {r['status']} {r['body']}")
    assert r["status"] == 200
    assert isinstance(r["body"], list)
    assert len(r["body"]) >= 2

    # POST /books
    r = wc.invoke_api(
        session, api_id=api_id, path="/books", method="POST",
        body={"title": "X", "author": "Y"},
        access_token=token["access_token"],
    )
    print(f"[6c] POST /books -> {r['status']} {r['body']}")
    assert r["status"] == 201
    new_id = r["body"]["id"]

    # GET /books/:id
    r = wc.invoke_api(session, api_id=api_id, path=f"/books/{new_id}", access_token=token["access_token"])
    print(f"[6d] /books/{new_id} -> {r['status']} {r['body']}")
    assert r["status"] == 200

    # Save api_id for the persistence test
    Path("/tmp/wso2_test_api_id").write_text(api_id)
    print(f"\nDeploy SUCCESS — api_id={api_id} saved for persistence check")
