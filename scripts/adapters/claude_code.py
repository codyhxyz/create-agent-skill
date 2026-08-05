#!/usr/bin/env python3
"""Optional Claude Code implementation of the create-agent-skill runner protocol.

Requires the ``claude`` executable and its normal local authentication. This
adapter is intentionally separate from the portable runner core.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def _environment() -> dict[str, str]:
    # Claude Code prevents accidental interactive nesting. This adapter starts
    # a deliberate noninteractive subprocess, matching the upstream behavior.
    return {key: value for key, value in os.environ.items() if key != "CLAUDECODE"}


def _generate(request: dict[str, Any]) -> dict[str, str]:
    prompt = request.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError("generate request requires string field 'prompt'")

    command = ["claude", "-p", "--output-format", "text"]
    model = request.get("model")
    if model:
        command.extend(["--model", str(model)])
    result = subprocess.run(
        command,
        input=prompt,
        capture_output=True,
        text=True,
        env=_environment(),
        timeout=int(request.get("timeout", 300)),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"claude exited {result.returncode}")
    return {"text": result.stdout}


def _trigger(request: dict[str, Any]) -> dict[str, bool]:
    query = request.get("query")
    skill_name = request.get("skill_name")
    description = request.get("skill_description")
    if not all(isinstance(value, str) for value in (query, skill_name, description)):
        raise ValueError(
            "trigger request requires string fields 'query', 'skill_name', and "
            "'skill_description'"
        )

    project_root = Path(request.get("project_root") or Path.cwd()).resolve()
    timeout = int(request.get("timeout", 30))
    unique_name = f"{skill_name}-skill-{uuid.uuid4().hex[:8]}"
    commands_dir = project_root / ".claude" / "commands"
    command_file = commands_dir / f"{unique_name}.md"
    process: subprocess.Popen[bytes] | None = None

    try:
        commands_dir.mkdir(parents=True, exist_ok=True)
        indented_description = "\n  ".join(description.splitlines())
        command_file.write_text(
            "---\n"
            "description: |\n"
            f"  {indented_description}\n"
            "---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {description}\n"
        )

        command = [
            "claude",
            "-p",
            query,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        model = request.get("model")
        if model:
            command.extend(["--model", str(model)])

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root,
            env=_environment(),
        )
        assert process.stdout is not None
        deadline = time.monotonic() + timeout
        buffer = ""
        pending_tool = False
        accumulated_input = ""

        while time.monotonic() < deadline:
            if process.poll() is not None:
                remainder = process.stdout.read()
                if remainder:
                    buffer += remainder.decode("utf-8", errors="replace")
                # A complete final line may not end in a newline.
                buffer += "\n"
            else:
                ready, _, _ = select.select([process.stdout], [], [], 0.5)
                if not ready:
                    continue
                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    continue
                buffer += chunk.decode("utf-8", errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "stream_event":
                    stream_event = event.get("event", {})
                    event_type = stream_event.get("type")
                    if event_type == "content_block_start":
                        block = stream_event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            pending_tool = block.get("name") in ("Skill", "Read")
                            accumulated_input = ""
                            if not pending_tool:
                                return {"triggered": False}
                    elif event_type == "content_block_delta" and pending_tool:
                        delta = stream_event.get("delta", {})
                        if delta.get("type") == "input_json_delta":
                            accumulated_input += delta.get("partial_json", "")
                            if unique_name in accumulated_input:
                                return {"triggered": True}
                    elif event_type in ("content_block_stop", "message_stop"):
                        if pending_tool:
                            return {"triggered": unique_name in accumulated_input}
                        if event_type == "message_stop":
                            return {"triggered": False}

                elif event.get("type") == "assistant":
                    for item in event.get("message", {}).get("content", []):
                        if item.get("type") != "tool_use":
                            continue
                        tool_input = item.get("input", {})
                        if item.get("name") == "Skill":
                            return {"triggered": unique_name in tool_input.get("skill", "")}
                        if item.get("name") == "Read":
                            return {"triggered": unique_name in tool_input.get("file_path", "")}
                        return {"triggered": False}
                elif event.get("type") == "result":
                    return {"triggered": False}

            if process.poll() is not None:
                break

        return {"triggered": False}
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        command_file.unlink(missing_ok=True)


def main() -> int:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        operation = request.get("operation")
        if operation == "generate":
            response = _generate(request)
        elif operation == "trigger":
            response = _trigger(request)
        else:
            raise ValueError("operation must be 'generate' or 'trigger'")
        json.dump(response, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print(f"Claude Code adapter error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
