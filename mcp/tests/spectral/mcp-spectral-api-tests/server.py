"""MCP server exposing Spectral API lint/security checks."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

SERVER_DIR = Path(__file__).resolve().parent
TECHNOLOGY_DIR = SERVER_DIR.parents[1] if len(SERVER_DIR.parents) > 1 else SERVER_DIR
HOST_DEFAULT_API_PATH = (
    TECHNOLOGY_DIR / "apic" / "mcp-apic-deploy-http" / "assets" / "branchesmock_1.0.0.yaml"
)
DEFAULT_API_PATH = Path(os.environ.get("SPECTRAL_DEFAULT_API_PATH", HOST_DEFAULT_API_PATH))
DEFAULT_RULESET_PATH = SERVER_DIR / ".spectral.yaml"

mcp = FastMCP(
    "spectral-api-tests",
    host="0.0.0.0",
    port=int(os.environ.get("SPECTRAL_MCP_PORT", "8771")),
)


def _resolve_path(path: str | None, default: Path) -> Path:
    candidate = Path(path).expanduser() if path else default
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"Path does not exist: {candidate}")
    return candidate


def _spectral_env() -> dict[str, str]:
    env = os.environ.copy()
    local_bin = SERVER_DIR / "node_modules" / ".bin"
    env["PATH"] = f"{local_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _spectral_command() -> str:
    local_spectral = SERVER_DIR / "node_modules" / ".bin" / "spectral"
    if local_spectral.exists():
        return str(local_spectral)
    return os.environ.get("SPECTRAL_BIN", "spectral")


def _run_spectral(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_spectral_command(), *args],
        cwd=SERVER_DIR,
        env=_spectral_env(),
        text=True,
        capture_output=True,
        timeout=int(os.environ.get("SPECTRAL_TIMEOUT_SECONDS", "60")),
        check=False,
    )


def _parse_spectral_result(
    result: subprocess.CompletedProcess[str],
    api: Path,
    ruleset: Path,
    fail_severity: str,
) -> dict[str, Any]:
    stdout = result.stdout.strip()
    try:
        findings = json.JSONDecoder().raw_decode(stdout)[0] if stdout else []
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Spectral returned non-JSON output with code {result.returncode}: {stdout}\n{result.stderr}"
        ) from exc

    summary = _summarize_findings(findings)
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "api_path": str(api),
        "ruleset_path": str(ruleset),
        "fail_severity": fail_severity,
        "summary": summary,
        "finding_count": len(findings),
        "findings": findings,
        "stderr": result.stderr.strip(),
    }


def _lint_api_path(api: Path, ruleset: Path, fail_severity: str) -> dict[str, Any]:
    result = _run_spectral(
        [
            "lint",
            str(api),
            "--ruleset",
            str(ruleset),
            "--format",
            "json",
            "--fail-severity",
            fail_severity,
        ]
    )
    return _parse_spectral_result(result, api, ruleset, fail_severity)


def _summarize_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"error": 0, "warn": 0, "info": 0, "hint": 0}
    severity_names = {0: "error", 1: "warn", 2: "info", 3: "hint"}
    for finding in findings:
        severity = finding.get("severity")
        name = severity_names.get(severity, str(severity))
        summary[name] = summary.get(name, 0) + 1
    return summary


@mcp.tool()
def spectral_version() -> dict[str, Any]:
    """Return the Spectral CLI version used by this server."""
    result = _run_spectral(["--version"])
    return {
        "command": _spectral_command(),
        "returncode": result.returncode,
        "version": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


@mcp.tool()
def spectral_lint_api(
    api_path: str | None = None,
    ruleset_path: str | None = None,
    fail_severity: str = "error",
) -> dict[str, Any]:
    """Run Spectral OpenAPI and OWASP API Security rules against an API spec."""
    api = _resolve_path(api_path, DEFAULT_API_PATH)
    ruleset = _resolve_path(ruleset_path, DEFAULT_RULESET_PATH)
    return _lint_api_path(api, ruleset, fail_severity)


@mcp.tool()
def spectral_lint_api_file(
    api_file: str,
    file_name: str = "openapi.yaml",
    ruleset_path: str | None = None,
    fail_severity: str = "error",
) -> dict[str, Any]:
    """Run Spectral against OpenAPI YAML/JSON content posted directly to the MCP tool."""
    if not api_file.strip():
        raise ValueError("api_file must contain OpenAPI YAML or JSON content.")

    suffix = Path(file_name).suffix or ".yaml"
    ruleset = _resolve_path(ruleset_path, DEFAULT_RULESET_PATH)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            prefix="spectral-api-",
            encoding="utf-8",
            delete=False,
        ) as temp_file:
            temp_file.write(api_file)
            temp_path = Path(temp_file.name)

        result = _lint_api_path(temp_path, ruleset, fail_severity)
        result["api_file_name"] = file_name
        return result
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@mcp.tool()
def spectral_lint_default_branchesmock() -> dict[str, Any]:
    """Run the default branchesmock_1.0.0.yaml test fixture."""
    return spectral_lint_api(str(DEFAULT_API_PATH), str(DEFAULT_RULESET_PATH))


if __name__ == "__main__":
    transport = os.environ.get("SPECTRAL_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
