"""MCP server exposing Postman/Newman API tests generated from OpenAPI."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import yaml
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

SERVER_DIR = Path(__file__).resolve().parent
DEFAULT_API_PATH = Path(
    os.environ.get("NEWMAN_DEFAULT_API_PATH", "/Users/casaroto/projetos/kong-demo/openapi-1.yaml")
)
DEFAULT_TARGET_URL = os.environ.get(
    "NEWMAN_DEFAULT_TARGET_URL", "https://localhost:8243/books-api/1.0.0/books"
)
DEFAULT_COLLECTIONS_DIR = Path(
    os.environ.get("NEWMAN_COLLECTIONS_DIR", SERVER_DIR / "collections")
)

mcp = FastMCP(
    "postman-newman-api-tests",
    host="0.0.0.0",
    port=int(os.environ.get("NEWMAN_MCP_PORT", "8772")),
)


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_value(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _resolve_path(path: str | None, default: Path) -> Path:
    candidate = Path(path).expanduser() if path else default
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"Path does not exist: {candidate}")
    return candidate


def _newman_env() -> dict[str, str]:
    env = os.environ.copy()
    local_bin = SERVER_DIR / "node_modules" / ".bin"
    env["PATH"] = f"{local_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _newman_command() -> str:
    local_newman = SERVER_DIR / "node_modules" / ".bin" / "newman"
    if local_newman.exists():
        return str(local_newman)
    return os.environ.get("NEWMAN_BIN", "newman")


def _load_openapi(api: Path) -> dict[str, Any]:
    with api.open("r", encoding="utf-8") as api_file:
        return _parse_openapi(api_file.read())


def _parse_openapi(api_file: str) -> dict[str, Any]:
    document = yaml.safe_load(api_file)
    if not isinstance(document, dict):
        raise ValueError("OpenAPI file must contain an object.")
    if not str(document.get("openapi", "")).startswith("3."):
        raise ValueError("Only OpenAPI 3.x documents are supported.")
    return document


def _path_to_request(path: str) -> str:
    return path.replace("{id}", "1").replace("{", "").replace("}", "")


def _sample_for_schema(schema: dict[str, Any] | None, name: str = "value") -> Any:
    if not schema:
        return f"sample-{name}"
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    schema_type = schema.get("type")
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return [_sample_for_schema(schema.get("items"), name)]
    if schema_type == "object" or "properties" in schema:
        required = schema.get("required") or []
        properties = schema.get("properties") or {}
        keys = required or list(properties)
        return {key: _sample_for_schema(properties.get(key), key) for key in keys}
    if name.lower() == "title":
        return "Newman Test Book"
    if name.lower() == "author":
        return "Postman MCP"
    return f"sample-{name}"


def _request_body(operation: dict[str, Any]) -> dict[str, Any] | None:
    body = operation.get("requestBody") or {}
    content = body.get("content") or {}
    json_content = content.get("application/json")
    if not json_content:
        return None
    return _sample_for_schema(json_content.get("schema"))


def _documented_statuses(operation: dict[str, Any]) -> list[int]:
    statuses: list[int] = []
    for status in (operation.get("responses") or {}).keys():
        if str(status).isdigit():
            statuses.append(int(status))
    return sorted(statuses) or [200]


def _has_json_response(operation: dict[str, Any]) -> bool:
    for response in (operation.get("responses") or {}).values():
        if not isinstance(response, dict):
            continue
        if "application/json" in (response.get("content") or {}):
            return True
    return False


def _target_base_url(target_url: str, openapi_paths: list[str]) -> str:
    target = target_url.rstrip("/")
    parts = urlsplit(target)
    normalized_paths = sorted((path.rstrip("/") for path in openapi_paths), key=len, reverse=True)
    for api_path in normalized_paths:
        if not api_path or api_path == "/":
            continue
        request_path = _path_to_request(api_path)
        if parts.path.rstrip("/").endswith(request_path.rstrip("/")):
            base_path = parts.path.rstrip()[: -len(request_path.rstrip("/"))] or "/"
            return urlunsplit((parts.scheme, parts.netloc, base_path.rstrip("/"), "", ""))
    return target


def _test_script(statuses: list[int], expect_json: bool, max_response_time_ms: int) -> str:
    lines = [
        "const documentedStatuses = " + json.dumps(statuses) + ";",
        "pm.test('status code is documented in OpenAPI', function () {",
        "  pm.expect(documentedStatuses).to.include(pm.response.code);",
        "});",
        f"pm.test('response time is under {max_response_time_ms}ms', function () {{",
        f"  pm.expect(pm.response.responseTime).to.be.below({max_response_time_ms});",
        "});",
    ]
    if expect_json:
        lines.extend(
            [
                "if (pm.response.text()) {",
                "  pm.test('response body is valid JSON', function () {",
                "    pm.response.to.be.json;",
                "  });",
                "}",
            ]
        )
    return "\n".join(lines)


def _build_collection(
    openapi: dict[str, Any],
    base_url: str,
    authorization: str | None,
    max_response_time_ms: int,
) -> dict[str, Any]:
    headers = [{"key": "Accept", "value": "application/json"}]
    if authorization:
        headers.append({"key": "Authorization", "value": authorization})

    items = []
    for path, path_item in (openapi.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(operation, dict):
                continue

            request_headers = list(headers)
            body_value = _request_body(operation)
            request: dict[str, Any] = {
                "method": method.upper(),
                "header": request_headers,
                "url": "{{baseUrl}}" + _path_to_request(path),
            }
            if body_value is not None:
                request_headers.append({"key": "Content-Type", "value": "application/json"})
                request["body"] = {"mode": "raw", "raw": json.dumps(body_value), "options": {"raw": {"language": "json"}}}

            items.append(
                {
                    "name": operation.get("operationId") or f"{method.upper()} {path}",
                    "request": request,
                    "event": [
                        {
                            "listen": "test",
                            "script": {
                                "type": "text/javascript",
                                "exec": _test_script(
                                    _documented_statuses(operation),
                                    _has_json_response(operation),
                                    max_response_time_ms,
                                ).splitlines(),
                            },
                        }
                    ],
                }
            )

    if not items:
        raise ValueError("OpenAPI document has no runnable operations under paths.")

    info = openapi.get("info") or {}
    return {
        "info": {
            "name": f"{info.get('title', 'OpenAPI')} Newman Tests",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": [{"key": "baseUrl", "value": base_url}],
    }


def _collection_file_name(openapi: dict[str, Any], source_name: str) -> str:
    title = ((openapi.get("info") or {}).get("title") or Path(source_name).stem or "openapi").lower()
    safe_title = "".join(character if character.isalnum() else "-" for character in title).strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{safe_title or 'openapi'}-{uuid4().hex[:8]}.postman_collection.json"


def _save_collection(
    collection: dict[str, Any],
    openapi: dict[str, Any],
    source_name: str,
    collections_dir: Path | None = None,
) -> Path:
    output_dir = collections_dir or DEFAULT_COLLECTIONS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    collection_path = output_dir / _collection_file_name(openapi, source_name)
    collection_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    return collection_path


def _run_newman(collection_path: Path, insecure: bool, timeout_seconds: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="newman-api-tests-") as temp_dir:
        temp_path = Path(temp_dir)
        report_path = temp_path / "newman-report.json"

        command = [
            _newman_command(),
            "run",
            str(collection_path),
            "--reporters",
            "json",
            "--reporter-json-export",
            str(report_path),
            "--timeout-request",
            str(timeout_seconds * 1000),
        ]
        if insecure:
            command.append("--insecure")

        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=SERVER_DIR,
            env=_newman_env(),
            text=True,
            capture_output=True,
            timeout=timeout_seconds + 30,
            check=False,
        )
        duration_ms = round((time.monotonic() - started) * 1000)

        report = {}
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))

        return {
            "returncode": result.returncode,
            "duration_ms": duration_ms,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "report": report,
        }


def _assertions_by_request(collection: dict[str, Any], newman_result: dict[str, Any]) -> list[dict[str, Any]]:
    run = (newman_result.get("report") or {}).get("run") or {}
    executions = run.get("executions") or []
    item_lookup = {item.get("name"): item.get("request", {}) for item in collection.get("item", [])}

    requests = []
    for execution in executions:
        item_name = ((execution.get("item") or {}).get("name")) or "Unnamed request"
        request = execution.get("request") or {}
        fallback_request = item_lookup.get(item_name, {})
        method = request.get("method") or fallback_request.get("method", "")
        url_value = request.get("url") or fallback_request.get("url", "")
        url = url_value.get("raw") if isinstance(url_value, dict) else url_value
        if not url:
            fallback_url = fallback_request.get("url", "")
            url = fallback_url.get("raw") if isinstance(fallback_url, dict) else fallback_url
        response = execution.get("response") or {}

        assertions = []
        for assertion in execution.get("assertions") or []:
            error = assertion.get("error")
            assertions.append(
                {
                    "assertion": assertion.get("assertion"),
                    "passed": not bool(error),
                    "error": error,
                }
            )

        requests.append(
            {
                "request": item_name,
                "method": method,
                "url": url,
                "status": response.get("code"),
                "response_time_ms": response.get("responseTime"),
                "assertion_count": len(assertions),
                "failed_assertion_count": len([assertion for assertion in assertions if not assertion["passed"]]),
                "assertions": assertions,
            }
        )
    return requests


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, dict):
        key = str(value.get("key", "")).lower()
        if key in {"authorization", "apikey", "api-key", "x-api-key", "internal-key"}:
            redacted = dict(value)
            redacted["value"] = "***REDACTED***"
            return redacted
        return {item_key: _redact_sensitive(item_value) for item_key, item_value in value.items()}
    return value


def _markdown_report(
    api_source: str,
    target_url: str,
    base_url: str,
    collection_path: Path,
    collection: dict[str, Any],
    newman_result: dict[str, Any],
) -> str:
    report = newman_result.get("report") or {}
    run = report.get("run") or {}
    stats = run.get("stats") or {}
    failures = run.get("failures") or []
    request_assertions = _assertions_by_request(collection, newman_result)

    lines = [
        "# Newman API Test Report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- API spec: `{api_source}`",
        f"- Target URL: `{target_url}`",
        f"- Derived base URL: `{base_url}`",
        f"- Saved collection: `{collection_path}`",
        f"- Collection items: {len(collection.get('item', []))}",
        f"- Newman return code: {newman_result.get('returncode')}",
        f"- Duration: {newman_result.get('duration_ms')} ms",
        "",
        "## Summary",
        "",
    ]

    for name, value in stats.items():
        if isinstance(value, dict):
            lines.append(
                f"- {name}: total={value.get('total', 0)}, failed={value.get('failed', 0)}, pending={value.get('pending', 0)}"
            )

    lines.extend(["", "## Requests and Assertions", ""])
    for request in request_assertions:
        lines.append(
            f"- {request['request']}: {request['method']} {request['url']} -> {request['status']} "
            f"({request['response_time_ms']} ms), assertions={request['assertion_count']}, "
            f"failed={request['failed_assertion_count']}"
        )
        for assertion in request["assertions"]:
            status = "passed" if assertion["passed"] else "failed"
            lines.append(f"  - {assertion['assertion']}: {status}")

    lines.extend(["", "## Failures", ""])
    if failures:
        for failure in failures:
            source = (failure.get("source") or {}).get("name") or (failure.get("parent") or {}).get("name") or "unknown"
            error = failure.get("error") or {}
            lines.append(f"- {source}: {error.get('name', 'Error')} - {error.get('message', '')}")
    else:
        lines.append("- None")

    if newman_result.get("stderr"):
        lines.extend(["", "## Newman stderr", "", "```text", newman_result["stderr"], "```"])

    return "\n".join(lines)


def _run_api_tests_from_openapi(
    openapi: dict[str, Any],
    api_source: str,
    target_url: str,
    authorization: str | None,
    insecure: bool,
    timeout_seconds: int,
    max_response_time_ms: int,
    collections_dir: str | None = None,
) -> dict[str, Any]:
    base_url = _target_base_url(target_url, list((openapi.get("paths") or {}).keys()))
    collection = _build_collection(openapi, base_url, authorization, max_response_time_ms)
    collection_path = _save_collection(
        collection,
        openapi,
        api_source,
        Path(collections_dir).expanduser().resolve() if collections_dir else None,
    )
    newman_result = _run_newman(collection_path, insecure, timeout_seconds)
    report_markdown = _markdown_report(api_source, target_url, base_url, collection_path, collection, newman_result)

    run = (newman_result.get("report") or {}).get("run") or {}
    stats = run.get("stats") or {}
    failures = run.get("failures") or []
    request_assertions = _assertions_by_request(collection, newman_result)

    return {
        "passed": newman_result["returncode"] == 0 and not failures,
        "api_source": api_source,
        "target_url": target_url,
        "base_url": base_url,
        "collection_path": str(collection_path),
        "collection_item_count": len(collection.get("item", [])),
        "summary": stats,
        "failure_count": len(failures),
        "failures": _redact_sensitive(failures),
        "assertions_by_request": request_assertions,
        "executions": _redact_sensitive(run.get("executions") or []),
        "report_markdown": report_markdown,
        "newman": {
            "returncode": newman_result["returncode"],
            "duration_ms": newman_result["duration_ms"],
            "stdout": newman_result["stdout"],
            "stderr": newman_result["stderr"],
        },
    }


async def _post_openapi_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    query = request.query_params

    if "application/json" in content_type:
        payload = await request.json()
        api_file = payload.get("api_file") or payload.get("openapi") or payload.get("spec")
        if isinstance(api_file, dict):
            api_file = json.dumps(api_file)
        return {
            "api_file": api_file,
            "file_name": payload.get("file_name", "openapi.yaml"),
            "target_url": payload.get("target_url", DEFAULT_TARGET_URL),
            "authorization": payload.get("authorization"),
            "insecure": _bool_value(payload.get("insecure"), True),
            "timeout_seconds": _int_value(payload.get("timeout_seconds"), 60),
            "max_response_time_ms": _int_value(payload.get("max_response_time_ms"), 5000),
            "collections_dir": payload.get("collections_dir"),
        }

    api_file = (await request.body()).decode("utf-8")
    return {
        "api_file": api_file,
        "file_name": query.get("file_name", "openapi.yaml"),
        "target_url": query.get("target_url", DEFAULT_TARGET_URL),
        "authorization": request.headers.get("authorization") or query.get("authorization"),
        "insecure": _bool_value(query.get("insecure"), True),
        "timeout_seconds": _int_value(query.get("timeout_seconds"), 60),
        "max_response_time_ms": _int_value(query.get("max_response_time_ms"), 5000),
        "collections_dir": query.get("collections_dir"),
    }


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health(_: Request) -> JSONResponse:
    """Return a simple health response for HTTP deployments."""
    return JSONResponse({"status": "ok", "service": "postman-newman-api-tests"})


@mcp.custom_route("/api-tests/openapi", methods=["POST"])
async def post_openapi_tests(request: Request) -> JSONResponse:
    """Run API tests from a complete OpenAPI spec posted over HTTP."""
    try:
        payload = await _post_openapi_payload(request)
        api_file = payload["api_file"]
        if not api_file or not str(api_file).strip():
            return JSONResponse({"error": "api_file, openapi, spec, or raw request body is required."}, status_code=400)

        result = newman_run_api_tests_file(**payload)
        status_code = 200 if result["passed"] else 422
        return JSONResponse(result, status_code=status_code)
    except Exception as exc:
        return JSONResponse({"error": str(exc), "type": type(exc).__name__}, status_code=500)


@mcp.tool()
def newman_version() -> dict[str, Any]:
    """Return the Newman CLI version used by this server."""
    result = subprocess.run(
        [_newman_command(), "--version"],
        cwd=SERVER_DIR,
        env=_newman_env(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return {
        "command": _newman_command(),
        "returncode": result.returncode,
        "version": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


@mcp.tool()
def newman_run_api_tests(
    api_path: str | None = None,
    target_url: str = DEFAULT_TARGET_URL,
    authorization: str | None = None,
    insecure: bool = True,
    timeout_seconds: int = 60,
    max_response_time_ms: int = 5000,
) -> dict[str, Any]:
    """Generate a Postman collection from OpenAPI, run it with Newman, and return a complete report."""
    api = _resolve_path(api_path, DEFAULT_API_PATH)
    openapi = _load_openapi(api)
    result = _run_api_tests_from_openapi(
        openapi,
        str(api),
        target_url,
        authorization,
        insecure,
        timeout_seconds,
        max_response_time_ms,
    )
    result["api_path"] = str(api)
    return result


@mcp.tool()
def newman_run_api_tests_file(
    api_file: str,
    file_name: str = "openapi.yaml",
    target_url: str = DEFAULT_TARGET_URL,
    authorization: str | None = None,
    insecure: bool = True,
    timeout_seconds: int = 60,
    max_response_time_ms: int = 5000,
    collections_dir: str | None = None,
) -> dict[str, Any]:
    """Generate and run Newman API tests from OpenAPI YAML/JSON content supplied directly."""
    if not api_file.strip():
        raise ValueError("api_file must contain OpenAPI YAML or JSON content.")
    openapi = _parse_openapi(api_file)
    return _run_api_tests_from_openapi(
        openapi,
        file_name,
        target_url,
        authorization,
        insecure,
        timeout_seconds,
        max_response_time_ms,
        collections_dir,
    )


if __name__ == "__main__":
    transport = os.environ.get("NEWMAN_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
