#!/usr/bin/env python3
"""Configure an explicitly supplied Burp MCP transport for Codex."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    transport = ap.add_mutually_exclusive_group(required=True)
    transport.add_argument("--url", help="streamable HTTP MCP endpoint")
    transport.add_argument("--jar", help="local executable Burp MCP JAR")
    transport.add_argument("--command", help="stdio command string")
    ap.add_argument("--name", default="burp", help="Codex MCP server name")
    ap.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--replace", action="store_true",
                    help="explicitly remove and replace an existing server (default: fail safely)")
    ap.add_argument("--dry-run", action="store_true", help="print commands without changing Codex config")
    return ap


def build_add(args):
    command = ["codex", "mcp", "add", args.name]
    for item in args.env:
        if "=" not in item:
            raise ValueError(f"invalid --env value: {item!r}")
        command.extend(["--env", item])
    if args.url:
        command.extend(["--url", args.url])
    elif args.jar:
        jar = Path(args.jar).expanduser().resolve()
        if not jar.is_file():
            raise FileNotFoundError(f"Burp MCP JAR not found: {jar}")
        java = shutil.which("java")
        if not java:
            raise FileNotFoundError("java is required for --jar")
        command.extend(["--", java, "-jar", str(jar)])
    else:
        parts = shlex.split(args.command, posix=os.name != "nt")
        if not parts:
            raise ValueError("--command cannot be empty")
        command.extend(["--", *parts])
    return command


def main(argv=None):
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    if not shutil.which("codex"):
        argument_parser.error("Codex CLI is required on PATH")
    try:
        add = build_add(args)
    except (FileNotFoundError, ValueError) as error:
        argument_parser.error(str(error))

    exists = subprocess.run(
        ["codex", "mcp", "get", args.name], capture_output=True, text=True, check=False
    ).returncode == 0
    commands = []
    if exists:
        if not args.replace:
            argument_parser.error(f"MCP server {args.name!r} already exists")
        commands.append(["codex", "mcp", "remove", args.name])
    commands.append(add)

    if args.dry_run:
        print(json.dumps(commands, indent=2))
        return 0
    for command in commands:
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            return completed.returncode
    print(f"Configured Codex MCP server {args.name!r}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
