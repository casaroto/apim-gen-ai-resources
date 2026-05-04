"""After a docker restart, verify the BooksAPI deployed by test_e2e.py is still present and callable."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import wso2_client as wc  # noqa: E402

API_NAME = "BooksAPI"
API_VERSION = "1.0.0"


@pytest.fixture(scope="session")
def session():
    s = wc.WSO2Session()
    wc.login(s)
    return s


def test_api_persists_after_restart(session):
    saved = Path("/tmp/wso2_test_api_id").read_text().strip()
    print(f"\nLooking for previously-deployed api_id={saved}")

    api = wc.find_api(session, API_NAME, API_VERSION)
    assert api is not None, "BooksAPI:1.0.0 not found after restart — persistence FAILED"
    assert api["id"] == saved, f"api_id changed: was {saved}, now {api['id']} (different DB?)"

    print(f"[OK] api persisted with same id {api['id']}, lifecycle={api.get('lifeCycleStatus')}")
    assert api.get("lifeCycleStatus") == "PUBLISHED"

    # Hit the gateway to confirm the runtime config also persisted
    sub = wc.create_subscription(session, api["id"], app_name="books-test-app")
    token = wc.get_access_token(sub["consumer_key"], sub["consumer_secret"])
    time.sleep(5)
    r = wc.invoke_api(session, api_id=api["id"], path="/health", access_token=token["access_token"])
    print(f"gateway /health -> {r['status']} {r['body']}")
    assert r["status"] == 200

    r = wc.invoke_api(session, api_id=api["id"], path="/books", access_token=token["access_token"])
    print(f"gateway /books -> {r['status']} {len(r['body'])} books")
    assert r["status"] == 200
    assert isinstance(r["body"], list)
