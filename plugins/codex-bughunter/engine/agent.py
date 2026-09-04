#!/usr/bin/env python3
"""Codex subprocess adapter for the model-driven hunt and validation phases."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
SCHEMAS = ENGINE / "schemas"
SCHEMA_FILES = {
    "hunt": SCHEMAS / "hunt-result.schema.json",
    "validate": SCHEMAS / "validate-result.schema.json",
}


def _result_envelope(started, result="", error=None):
    return {
        "result": result,
        "error": error,
        "duration_s": round(time.time() - started, 1),
    }


def build_command(*, output_path, schema=None, model=None, cwd=None, skills_on=True,
                  sandbox="read-only"):
    """Build an argument-array command without shell interpolation."""
    cmd = [
        "codex", "exec", "--ephemeral", "--skip-git-repo-check",
        "--color", "never", "--sandbox", sandbox,
        "--output-last-message", str(output_path),
    ]
    if cwd:
        cmd.extend(["--cd", str(Path(cwd).resolve())])
    if schema:
        schema_path = SCHEMA_FILES.get(schema, Path(schema))
        if not schema_path.is_file():
            raise ValueError(f"unknown or missing output schema: {schema}")
        cmd.extend(["--output-schema", str(schema_path)])
    if model:
        cmd.extend(["--model", model])
    if not skills_on:
        cmd.append("--ignore-user-config")
    cmd.append("-")
    return cmd


def run_agent(task, skills_on=True, model=None, max_turns=None, timeout=600,
              schema=None, cwd=None, sandbox="read-only"):
    """Run Codex non-interactively and return a stable engine result envelope.

    ``max_turns`` remains accepted for callers migrating from the upstream
    adapter; Codex CLI does not expose an equivalent flag, so timeout is the
    bounded execution control.
    """
    del max_turns
    t0 = time.time()
    fd, output_name = tempfile.mkstemp(prefix="cbh-codex-", suffix=".txt")
    os.close(fd)
    try:
        cmd = build_command(
            output_path=output_name,
            schema=schema,
            model=model,
            cwd=cwd,
            skills_on=skills_on,
            sandbox=sandbox,
        )
        try:
            proc = subprocess.run(
                cmd,
                input=task,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _result_envelope(t0, error="timeout")
        except (FileNotFoundError, OSError) as error:
            return _result_envelope(t0, error=f"exec:{error}")

        result = Path(output_name).read_text(encoding="utf-8", errors="replace").strip()
        diagnostic = (proc.stderr or proc.stdout or "").strip()
        if proc.returncode != 0:
            lowered = diagnostic.lower()
            if "usage limit" in lowered or "session limit" in lowered or "rate limit" in lowered:
                return _result_envelope(t0, result, "rate-limited")
            summary = diagnostic.splitlines()[-1][:240] if diagnostic else f"exit {proc.returncode}"
            return _result_envelope(t0, result, f"exec:{summary}")
        if not result:
            return _result_envelope(t0, error="empty-result")
        if schema:
            try:
                json.loads(result)
            except json.JSONDecodeError as error:
                return _result_envelope(t0, result[:300], f"parse:{error}")
        return _result_envelope(t0, result)
    finally:
        try:
            os.remove(output_name)
        except FileNotFoundError:
            pass


def extract_json(text):
    """Pull the last valid JSON array/object out of an agent reply."""
    if not text:
        return None
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    blocks += re.findall(r"```\s*(\[.*?\]|\{.*?\})\s*```", text, re.S)
    for b in reversed(blocks):
        try:
            return json.loads(b.strip())
        except Exception:
            pass
    for b in reversed(re.findall(r"(\[.*\]|\{.*\})", text, re.S)):
        try:
            return json.loads(b)
        except Exception:
            pass
    return None


if __name__ == "__main__":
    # offline self-test of the JSON extractor (no agent call)
    assert extract_json('blah ```json\n[{"a":1}]\n``` end') == [{"a": 1}]
    assert extract_json('text {"x": "y"} more') == {"x": "y"}
    assert extract_json("no json here") is None
    assert extract_json('first {"a":1} then ```json\n{"b":2}\n```') == {"b": 2}  # prefers fenced/last
    cmd = build_command(output_path="out.txt", schema="hunt", cwd=ENGINE)
    assert cmd[:2] == ["codex", "exec"] and cmd[-1] == "-"
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    print("agent.py extractor self-test: PASS")
