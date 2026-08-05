"""Protocol helpers for configurable Agent Skill runner commands."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any

RUNNER_ENV = "AGENT_SKILL_RUNNER"


def resolve_runner(explicit: str | None) -> str:
    """Return an explicit runner or the configured environment value."""
    command = explicit or os.environ.get(RUNNER_ENV)
    if not command:
        raise ValueError(
            f"No runner configured. Pass --runner or set {RUNNER_ENV}. "
            "See SKILL.md for the JSON protocol."
        )
    if not shlex.split(command):
        raise ValueError("Runner command is empty")
    return command


def call_runner(command: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """Send one JSON request to a runner and parse its JSON response.

    The command is split with shell-like quoting but is executed without a
    shell, avoiding interpolation of prompts or other payload values.
    """
    try:
        result = subprocess.run(
            shlex.split(command),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Runner executable not found: {shlex.split(command)[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Runner timed out after {timeout} seconds") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise RuntimeError(f"Runner exited {result.returncode}: {detail}")

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Runner did not return a JSON object on stdout") from exc
    if not isinstance(response, dict):
        raise RuntimeError("Runner response must be a JSON object")
    return response


def trigger_runner(command: str, payload: dict[str, Any], timeout: int) -> bool:
    """Call a runner's trigger operation and validate its response."""
    response = call_runner(command, {"operation": "trigger", **payload}, timeout)
    if not isinstance(response.get("triggered"), bool):
        raise RuntimeError("Trigger runner response requires boolean field 'triggered'")
    return response["triggered"]


def generate_runner(command: str, prompt: str, model: str | None, timeout: int) -> str:
    """Call a runner's text-generation operation and validate its response."""
    response = call_runner(
        command,
        {"operation": "generate", "prompt": prompt, "model": model},
        timeout,
    )
    if not isinstance(response.get("text"), str):
        raise RuntimeError("Generate runner response requires string field 'text'")
    return response["text"]
