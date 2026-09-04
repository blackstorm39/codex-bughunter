from __future__ import annotations

import importlib.util
import io
import json
import ntpath
import os
import subprocess
import sys
import tempfile
import threading
import textwrap
import unittest
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "codex-bughunter"
sys.path.insert(0, str(PLUGIN))

from cbh import __version__ as cbh_version  # noqa: E402
from cbh import cli  # noqa: E402
from engine import agent, memory, recon  # noqa: E402
from engine.engine import Engine  # noqa: E402
from engine.scope import Scope  # noqa: E402

PLUGIN_NAME = "codex-bughunter"
MARKETPLACE_NAME = "codex-bughunter-local"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
PLUGIN_VERSION = "2.1.1"
CANONICAL_REPO = "https://git.ot9.me/Adminx/codex-bughunter"
CANONICAL_DOCS = (
    "https://git.ot9.me/Adminx/codex-bughunter/src/branch/main/"
    "plugins/codex-bughunter/docs/cbh-cli.md"
)
RELEASE_SURFACES = (
    ROOT / "README.md",
    ROOT / "docs/development-roadmap.md",
    ROOT / "docs/project-changelog.md",
    PLUGIN / ".codex-plugin/plugin.json",
    PLUGIN / "README.md",
    PLUGIN / "INSTALL.md",
    PLUGIN / "CHANGELOG.md",
    PLUGIN / "pyproject.toml",
    PLUGIN / "docs/_config.yml",
    PLUGIN / "docs/recon-manifest.md",
    PLUGIN / "docs/multi-harness.md",
)

_MCP_SPEC = importlib.util.spec_from_file_location(
    "cbh_setup_harness_mcp", PLUGIN / "scripts/setup_harness_mcp.py"
)
assert _MCP_SPEC and _MCP_SPEC.loader
mcp_setup = importlib.util.module_from_spec(_MCP_SPEC)
_MCP_SPEC.loader.exec_module(mcp_setup)


def _normalize_path(path: str) -> str:
    cleaned = path
    if cleaned.startswith("\\\\?\\UNC\\"):
        cleaned = "\\\\" + cleaned[8:]
    elif cleaned.startswith("\\\\?\\"):
        cleaned = cleaned[4:]
    return os.path.normcase(os.path.abspath(cleaned))


class FakeCodexHarness:
    def __init__(self, marketplaces, installed=None, available=None, overrides=None):
        self.marketplaces = marketplaces
        self.installed = installed or []
        self.available = available or []
        self.overrides = overrides or {}
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.log_path = self.root / "codex-log.json"
        self.python_path = self.root / "fake_codex.py"
        self.cmd_path = self.root / "codex.cmd"
        self.sh_path = self.root / "codex"
        self._write_files()

    def _write_files(self):
        script = textwrap.dedent(
            """
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            log_path = Path(os.environ["FAKE_CODEX_LOG"])
            entries = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
            entries.append(args)
            log_path.write_text(json.dumps(entries), encoding="utf-8")

            overrides = json.loads(os.environ.get("FAKE_CODEX_OVERRIDES", "{}"))
            key = " ".join(args)
            if key in overrides:
                override = overrides[key]
                stdout = override.get("stdout", "")
                stderr = override.get("stderr", "")
                if stdout:
                    print(stdout, end="")
                if stderr:
                    print(stderr, end="", file=sys.stderr)
                raise SystemExit(int(override.get("exit_code", 0)))

            marketplaces = json.loads(os.environ.get("FAKE_CODEX_MARKETPLACES", "[]"))
            installed = json.loads(os.environ.get("FAKE_CODEX_INSTALLED", "[]"))
            available = json.loads(os.environ.get("FAKE_CODEX_AVAILABLE", "[]"))

            if args == ["plugin", "marketplace", "list", "--json"]:
                print(json.dumps({"marketplaces": marketplaces}))
                raise SystemExit(0)
            if args == ["plugin", "list", "--json"]:
                print(json.dumps({"installed": installed}))
                raise SystemExit(0)
            if args == ["plugin", "list", "--available", "--json"]:
                print(json.dumps({"available": available}))
                raise SystemExit(0)
            if len(args) == 5 and args[:3] == ["plugin", "marketplace", "add"] and args[4] == "--json":
                print(json.dumps({"ok": True, "root": args[3]}))
                raise SystemExit(0)
            if len(args) == 5 and args[:3] == ["plugin", "marketplace", "remove"] and args[4] == "--json":
                print(json.dumps({"ok": True, "marketplace": args[3]}))
                raise SystemExit(0)
            if len(args) == 4 and args[:2] == ["plugin", "add"] and args[3] == "--json":
                print(json.dumps({"ok": True, "pluginId": args[2]}))
                raise SystemExit(0)
            if len(args) == 4 and args[:2] == ["plugin", "remove"] and args[3] == "--json":
                print(json.dumps({"ok": True, "pluginId": args[2]}))
                raise SystemExit(0)

            print("unexpected fake codex args: " + " ".join(args), file=sys.stderr)
            raise SystemExit(64)
            """
        ).strip()
        self.python_path.write_text(script + "\n", encoding="utf-8")
        self.cmd_path.write_text(
            f'@echo off\r\n"{sys.executable}" "%~dp0fake_codex.py" %*\r\n',
            encoding="utf-8",
        )
        self.sh_path.write_text(
            "#!/usr/bin/env sh\n"
            f'exec "{sys.executable}" "$(dirname "$0")/fake_codex.py" "$@"\n',
            encoding="utf-8",
        )
        self.sh_path.chmod(0o755)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        self.cleanup()

    def env(self):
        env = os.environ.copy()
        env["PATH"] = str(self.root) + os.pathsep + env.get("PATH", "")
        env["FAKE_CODEX_LOG"] = str(self.log_path)
        env["FAKE_CODEX_MARKETPLACES"] = json.dumps(self.marketplaces)
        env["FAKE_CODEX_INSTALLED"] = json.dumps(self.installed)
        env["FAKE_CODEX_AVAILABLE"] = json.dumps(self.available)
        env["FAKE_CODEX_OVERRIDES"] = json.dumps(self.overrides)
        return env

    def commands(self):
        if not self.log_path.exists():
            return []
        return json.loads(self.log_path.read_text(encoding="utf-8"))

    def cleanup(self):
        self.temp_dir.cleanup()


class PluginContractTests(unittest.TestCase):
    def test_marketplace_and_manifest_are_codex_native(self):
        marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(marketplace["name"], MARKETPLACE_NAME)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], PLUGIN_NAME)
        self.assertEqual(entry["source"]["path"], f"./plugins/{PLUGIN_NAME}")
        self.assertEqual(entry["source"]["source"], "local")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Security")
        self.assertEqual(PLUGIN.name, PLUGIN_NAME)

        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], PLUGIN_NAME)
        self.assertEqual(manifest["version"], PLUGIN_VERSION)
        self.assertEqual(manifest["skills"].rstrip("/"), "./skills")
        self.assertEqual(manifest["homepage"], CANONICAL_REPO)
        self.assertEqual(manifest["repository"], CANONICAL_REPO)
        self.assertEqual(manifest["interface"]["websiteURL"], CANONICAL_REPO)
        self.assertEqual(
            manifest["interface"]["privacyPolicyURL"],
            f"{CANONICAL_REPO}/src/branch/main/plugins/codex-bughunter/SECURITY.md",
        )
        self.assertEqual(
            manifest["interface"]["termsOfServiceURL"],
            f"{CANONICAL_REPO}/src/branch/main/plugins/codex-bughunter/LICENSE-CONTENT",
        )
        prompts = manifest["interface"]["defaultPrompt"]
        self.assertEqual(len(prompts), 3)
        self.assertTrue(all(isinstance(prompt, str) for prompt in prompts))
        self.assertTrue(all(0 < len(prompt) <= 128 for prompt in prompts))
        self.assertTrue((PLUGIN / manifest["interface"]["logo"].removeprefix("./")).is_file())

        pyproject = (PLUGIN / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{PLUGIN_VERSION}"', pyproject)
        self.assertIn(f'Homepage = "{CANONICAL_REPO}"', pyproject)
        self.assertIn(f'Documentation = "{CANONICAL_DOCS}"', pyproject)
        self.assertEqual(cli.REPO_URL, CANONICAL_REPO)
        self.assertEqual(cli.PRODUCER, f"cbh-recon/{PLUGIN_VERSION}")
        self.assertEqual(cbh_version, PLUGIN_VERSION)

    def test_release_surfaces_use_canonical_fork_urls(self):
        stale_host = "gitea" + ".local"
        for path in RELEASE_SURFACES:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(stale_host, text)

    def test_expected_skill_inventory_and_explicit_workflows(self):
        skill_dirs = sorted(path.parent for path in (PLUGIN / "skills").glob("*/SKILL.md"))
        workflows = [path for path in skill_dirs if path.name.startswith("workflow-")]
        domains = [path for path in skill_dirs if not path.name.startswith("workflow-")]
        self.assertEqual(len(domains), 83)
        self.assertEqual(len(workflows), 15)
        for workflow in workflows:
            skill_text = (workflow / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("user-invocable: true", skill_text)
            self.assertIn(f"$codex-bughunter:{workflow.name}", skill_text)
            metadata = (workflow / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn("allow_implicit_invocation: false", metadata)

        index = json.loads((PLUGIN / "cbh/data/skill_index.json").read_text(encoding="utf-8"))
        for name in (path.name for path in workflows):
            self.assertNotIn("user-invocable", index["skills"][name])

    def test_path_normalization_handles_unc_and_extended_drive_prefixes(self):
        if os.name != "nt":
            self.skipTest("Windows path normalization coverage is host-specific.")
        self.assertEqual(
            _normalize_path(r"\\?\UNC\server\share\repo"),
            ntpath.normcase(ntpath.abspath(r"\\server\share\repo")),
        )
        self.assertEqual(
            _normalize_path(r"\\?\C:\temp\repo"),
            ntpath.normcase(ntpath.abspath(r"C:\temp\repo")),
        )

    def test_powershell_normalize_local_path_handles_unc_and_extended_drive_prefixes(self):
        if os.name != "nt":
            self.skipTest("Windows path normalization coverage is host-specific.")

        function_body = self._powershell_function("Normalize-LocalPath")
        completed = subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-Command",
                (
                    f"{function_body}\n"
                    "$paths = @(\n"
                    "  (Normalize-LocalPath '\\\\?\\UNC\\server\\share\\repo')\n"
                    "  (Normalize-LocalPath '\\\\?\\C:\\temp\\repo')\n"
                    ")\n"
                    "$paths | ConvertTo-Json -Compress\n"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        normalized = json.loads(completed.stdout)
        self.assertEqual(
            ntpath.normcase(normalized[0]),
            ntpath.normcase(ntpath.abspath(r"\\server\share\repo")),
        )
        self.assertEqual(
            ntpath.normcase(normalized[1]),
            ntpath.normcase(ntpath.abspath(r"C:\temp\repo")),
        )

    def test_installers_add_missing_marketplace_before_refresh(self):
        def assertion(result, commands):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(commands[0], ["plugin", "marketplace", "list", "--json"])
            marketplace_add = self._command_with_prefix(commands, ["plugin", "marketplace", "add"])
            self.assertEqual(_normalize_path(marketplace_add[3]), _normalize_path(str(ROOT)))
            self.assertLess(
                commands.index(marketplace_add),
                commands.index(["plugin", "list", "--available", "--json"]),
            )
            self.assertIn(["plugin", "list", "--json"], commands)
            self.assertIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[],
                installed=[],
                available=[self._available_plugin_record()],
            ),
            assertion,
        )

    def test_installers_refresh_exact_installed_target(self):
        def assertion(result, commands):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(["plugin", "list", "--available", "--json"], commands)
            self.assertIn(["plugin", "list", "--json"], commands)
            self.assertIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[self._installed_plugin_record()],
                available=[],
            ),
            assertion,
        )

    def test_installers_validate_exact_available_target_source(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(PLUGIN_ID, result.stderr)
            self.assertNotIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[],
                available=[self._available_plugin_record(source_path="C:/tmp/not-this-plugin")],
            ),
            assertion,
        )

    def test_installers_fail_closed_on_wrong_installed_target_source(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(PLUGIN_ID, result.stderr)
            self.assertNotIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[self._installed_plugin_record(source_path="C:/tmp/not-this-plugin")],
                available=[],
            ),
            assertion,
        )

    def test_installers_ignore_same_name_from_other_marketplace(self):
        def assertion(result, commands):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[],
                available=[
                    {
                        "pluginId": "codex-bughunter@other-marketplace",
                        "name": PLUGIN_NAME,
                        "marketplaceName": "other-marketplace",
                        "source": {"source": "local", "path": "C:/tmp/other/plugins/codex-bughunter"},
                    },
                    self._available_plugin_record(),
                ],
            ),
            assertion,
        )

    def test_installers_fail_closed_on_marketplace_root_collision(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(MARKETPLACE_NAME, result.stderr)
            self.assertNotIn(["plugin", "marketplace", "add", str(ROOT), "--json"], commands)
            self.assertNotIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": "C:/tmp/not-this-repo"}],
                installed=[],
                available=[],
            ),
            assertion,
        )

    def test_installers_fail_closed_on_marketplace_list_failure_before_mutation(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            if result.args[0] == "sh":
                self.assertEqual(result.returncode, 9)
            self.assertEqual(commands, [["plugin", "marketplace", "list", "--json"]])

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[],
                installed=[],
                available=[self._available_plugin_record()],
                overrides={
                    "plugin marketplace list --json": {
                        "exit_code": 9,
                        "stdout": '{"marketplaces":[]}',
                        "stderr": "boom",
                    }
                },
            ),
            assertion,
        )

    def test_installers_fail_closed_on_available_list_failure_before_mutation(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            if result.args[0] == "sh":
                self.assertEqual(result.returncode, 7)
            self.assertEqual(
                commands,
                [
                    ["plugin", "marketplace", "list", "--json"],
                    ["plugin", "list", "--available", "--json"],
                ],
            )

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[],
                available=[self._available_plugin_record()],
                overrides={
                    "plugin list --available --json": {
                        "exit_code": 7,
                        "stdout": '{"installed":[],"available":[]}',
                        "stderr": "broken",
                    }
                },
            ),
            assertion,
        )

    def test_installers_fail_closed_on_empty_json(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[],
                installed=[],
                available=[self._available_plugin_record()],
                overrides={"plugin marketplace list --json": {"exit_code": 0, "stdout": ""}},
            ),
            assertion,
        )

    def test_installers_fail_closed_on_malformed_json(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[],
                available=[self._available_plugin_record()],
                overrides={"plugin list --available --json": {"exit_code": 0, "stdout": "{oops"}},
            ),
            assertion,
        )

    def test_installers_fail_closed_on_non_object_json(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[],
                available=[self._available_plugin_record()],
                overrides={"plugin list --available --json": {"exit_code": 0, "stdout": "null"}},
            ),
            assertion,
        )

    def test_installers_fail_closed_on_wrong_shape_json(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(["plugin", "add", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[],
                available=[self._available_plugin_record()],
                overrides={"plugin list --available --json": {"exit_code": 0, "stdout": '{"available":"bad"}'}},
            ),
            assertion,
        )

    def test_uninstall_removes_exact_plugin_without_marketplace_flag(self):
        def assertion(result, commands):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(["plugin", "list", "--json"], commands)
            self.assertNotIn(["plugin", "list", "--available", "--json"], commands)
            self.assertIn(["plugin", "remove", PLUGIN_ID, "--json"], commands)
            self.assertNotIn(["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[self._installed_plugin_record()],
                available=[],
            ),
            assertion,
            installer_args=["--uninstall"],
        )

    def test_uninstall_removes_marketplace_only_when_requested(self):
        def assertion(result, commands):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(["plugin", "remove", PLUGIN_ID, "--json"], commands)
            self.assertIn(["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[self._installed_plugin_record()],
                available=[],
            ),
            assertion,
            installer_args=["--uninstall", "--remove-marketplace"],
        )

    def test_uninstall_ignores_available_only_record(self):
        def assertion(result, commands):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(["plugin", "list", "--json"], commands)
            self.assertNotIn(["plugin", "remove", PLUGIN_ID, "--json"], commands)

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[],
                available=[self._available_plugin_record()],
            ),
            assertion,
            installer_args=["--uninstall"],
        )

    def test_burp_conflict_fails_before_plugin_mutation(self):
        def assertion(result, commands):
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(commands, [])

        self._assert_each_installer(
            lambda: FakeCodexHarness(
                marketplaces=[{"name": MARKETPLACE_NAME, "root": str(ROOT)}],
                installed=[self._installed_plugin_record()],
                available=[],
            ),
            assertion,
            installer_args=["--burp-jar", "C:/tmp/burp.jar", "--burp-url", "http://127.0.0.1:9876/mcp"],
        )

    def _assert_each_installer(self, harness_factory, assertion, installer_args=None):
        for installer in ("powershell", "sh"):
            with self.subTest(installer=installer):
                with harness_factory() as harness:
                    result = self._run_installer(installer, harness, installer_args or [])
                    assertion(result, harness.commands())

    def _run_installer(self, installer: str, harness: FakeCodexHarness, args: list[str]):
        env = harness.env()
        if installer == "powershell":
            command = [
                "pwsh",
                "-NoProfile",
                "-File",
                str(PLUGIN / "scripts/install.ps1"),
                *self._powershell_args(args),
            ]
        else:
            command = ["sh", str(PLUGIN / "scripts/install.sh"), *args]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=env,
        )

    def _command_with_prefix(self, commands: list[list[str]], prefix: list[str]) -> list[str]:
        for command in commands:
            if command[: len(prefix)] == prefix:
                return command
        self.fail(f"Missing command with prefix {prefix!r} in {commands!r}")

    def _powershell_function(self, name: str) -> str:
        lines = (PLUGIN / "scripts/install.ps1").read_text(encoding="utf-8").splitlines()
        header = f"function {name} {{"
        block: list[str] = []
        collecting = False

        for line in lines:
            if not collecting:
                if line == header:
                    collecting = True
                    block.append(line)
                continue

            block.append(line)
            if line == "}":
                return "\n".join(block)

        self.fail(f"Could not find PowerShell function {name!r}")

    def _powershell_args(self, args: list[str]) -> list[str]:
        converted: list[str] = []
        index = 0
        while index < len(args):
            token = args[index]
            if token == "--uninstall":
                converted.append("-Uninstall")
                index += 1
                continue
            if token == "--remove-marketplace":
                converted.append("-RemoveMarketplace")
                index += 1
                continue
            if token == "--burp-jar":
                converted.extend(["-BurpJar", args[index + 1]])
                index += 2
                continue
            if token == "--burp-url":
                converted.extend(["-BurpUrl", args[index + 1]])
                index += 2
                continue
            raise ValueError(f"Unsupported installer test arg: {token}")
        return converted

    def _installed_plugin_record(self, source_path: str | None = None, marketplace_source: str | None = None):
        return {
            "pluginId": PLUGIN_ID,
            "name": PLUGIN_NAME,
            "marketplaceName": MARKETPLACE_NAME,
            "source": {"source": "local", "path": source_path or str(PLUGIN)},
            "marketplaceSource": {
                "sourceType": "local",
                "source": marketplace_source or str(ROOT),
            },
        }

    def _available_plugin_record(self, source_path: str | None = None, marketplace_source: str | None = None):
        return {
            "pluginId": PLUGIN_ID,
            "name": PLUGIN_NAME,
            "marketplaceName": MARKETPLACE_NAME,
            "source": {"source": "local", "path": source_path or str(PLUGIN)},
            "marketplaceSource": {
                "sourceType": "local",
                "source": marketplace_source or str(ROOT),
            },
        }


class RuntimeContractTests(unittest.TestCase):
    def test_codex_command_is_safe_and_schema_bound(self):
        command = agent.build_command(
            output_path="result.txt", schema="hunt", cwd=PLUGIN, skills_on=False
        )
        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertEqual(command[-1], "-")
        self.assertIn("--sandbox", command)
        self.assertIn("read-only", command)
        self.assertIn("--output-schema", command)
        self.assertIn("--ignore-user-config", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_scope_is_default_deny_and_deny_wins(self):
        scope = Scope(["example.com", "*.example.com"], ["admin.example.com"])
        self.assertTrue(scope.in_scope_host("https://api.example.com"))
        self.assertFalse(scope.in_scope_host("https://admin.example.com"))
        self.assertFalse(scope.in_scope_host("https://example.com.evil.test"))

    def test_scope_bare_host_is_exact_and_malformed_rules_fail_closed(self):
        exact = Scope(["api.example.com"])
        self.assertTrue(exact.in_scope_host("https://api.example.com"))
        self.assertFalse(exact.in_scope_host("https://nested.api.example.com"))
        for malformed in ("re:[", "999.0.0.0/8"):
            with self.subTest(pattern=malformed), self.assertRaises(ValueError):
                Scope(["example.com", "*.example.com"], [malformed])

    def test_engine_rejects_out_of_scope_seed_before_creating_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scope_path = Path(temp_dir) / "scope.json"
            scope_path.write_text(json.dumps({
                "name": "blocked", "in_scope": ["example.com"],
                "out_of_scope": [], "seeds": ["https://evil.test"],
            }), encoding="utf-8")
            state_root = Path(temp_dir) / "state"
            with self.assertRaisesRegex(ValueError, "out-of-scope seed"):
                Engine(scope_path, state_root, None, 1, 1, 1, mock=True)
            self.assertFalse(state_root.exists())

    def test_default_openapi_auth_sweep_is_get_only(self):
        methods = []

        class Handler(BaseHTTPRequestHandler):
            def _respond(self):
                methods.append(self.command)
                self.send_response(200)
                self.end_headers()

            do_GET = _respond
            do_POST = _respond
            do_PUT = _respond
            do_PATCH = _respond
            do_DELETE = _respond

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            spec = {"security": [{"token": []}], "paths": {"/resource": {
                "get": {}, "post": {}, "put": {}, "patch": {}, "delete": {},
            }}}
            recon.auth_enforcement_sweep(
                spec, f"http://127.0.0.1:{server.server_port}", log=lambda _msg: None
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(methods, ["GET"])

    def test_katana_is_restricted_to_the_seed_fqdn(self):
        completed = subprocess.CompletedProcess(["katana"], 0, "", "")
        scope = Scope(
            ["www.example.com"], ["admin.example.com"], ["https://www.example.com"]
        )
        with mock.patch.object(recon, "which", return_value="katana"), \
                mock.patch("subprocess.run", return_value=completed) as invoked:
            self.assertEqual(recon._katana_urls(scope, lambda _message: None), {})
        command = invoked.call_args.args[0]
        field_scope = command.index("-fs")
        self.assertEqual(command[field_scope + 1], "fqdn")

    def test_http_clients_do_not_follow_redirects(self):
        visits = {"redirect": 0, "destination": 0}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/redirect":
                    visits["redirect"] += 1
                    self.send_response(302)
                    self.send_header("Location", "/destination")
                    self.end_headers()
                else:
                    visits["destination"] += 1
                    self.send_response(200)
                    self.end_headers()

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/redirect"
        try:
            with mock.patch.dict(os.environ, {
                    "HTTP_PROXY": "", "HTTPS_PROXY": "", "CBH_BURP_PROXY": ""}, clear=False):
                cli.configure_http_proxy("")
                status, _, _ = cli.http_get(url)
            self.assertEqual(status, 302)
            _, final, _ = recon._get(url)
            self.assertEqual(final, url)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(visits, {"redirect": 2, "destination": 0})

    def test_successful_agent_result_can_contain_rate_limit_text(self):
        def completed(command, **_kwargs):
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text('{"evidence":"rate limit is enforced"}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(agent.subprocess, "run", side_effect=completed):
            result = agent.run_agent("test", schema="validate")
        self.assertIsNone(result["error"])
        self.assertIn("rate limit is enforced", result["result"])

    def test_mcp_setup_does_not_replace_existing_entry_by_default(self):
        existing = subprocess.CompletedProcess(["codex", "mcp", "get", "burp"], 0, "", "")
        with mock.patch.object(mcp_setup.shutil, "which", return_value="codex"), \
                mock.patch.object(mcp_setup.subprocess, "run", return_value=existing), \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            mcp_setup.main(["--url", "http://127.0.0.1:9876/mcp", "--dry-run"])
        self.assertEqual(raised.exception.code, 2)

    def test_recon_filters_discoveries_before_dns_or_http(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scope_path = Path(temp_dir) / "scope.json"
            scope_path.write_text(json.dumps({
                "in_scope": ["example.com", "*.example.com"],
                "out_of_scope": ["admin.example.com"],
                "seeds": ["https://example.com"],
            }), encoding="utf-8")
            resolved_hosts = []

            def resolve(host):
                resolved_hosts.append(host)
                return []

            args = SimpleNamespace(
                target="example.com", scope_file=str(scope_path), out=str(Path(temp_dir) / "recon"),
                proxy=None, burp=False,
            )
            with mock.patch.object(cli, "recon_subdomains_via_crtsh", return_value={
                    "api.example.com", "admin.example.com", "evil.test"}), \
                    mock.patch.object(cli, "recon_subdomains_via_subfinder", return_value=set()), \
                    mock.patch.object(cli, "recon_resolve", side_effect=resolve):
                self.assertEqual(cli.cmd_recon(args), 0)
            self.assertIn("example.com", resolved_hosts)
            self.assertIn("api.example.com", resolved_hosts)
            self.assertNotIn("admin.example.com", resolved_hosts)
            self.assertNotIn("evil.test", resolved_hosts)

    def test_memory_uses_codex_home_and_round_trips(self):
        old_memory = os.environ.pop("BUGHUNTER_MEMORY_DIR", None)
        old_cbh_home = os.environ.get("CBH_HOME")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["CBH_HOME"] = temp_dir
            try:
                finding = {
                    "url": "https://api.example.com/users?id=2",
                    "param": "id",
                    "vuln_class": "idor",
                    "severity": "high",
                }
                self.assertTrue(memory.record_finding(
                    "demo", "api.example.com", ["api"], finding,
                    {"severity": "high", "reason": "cross-account data"},
                ))
                self.assertTrue((Path(temp_dir) / "memory/findings.jsonl").is_file())
            finally:
                if old_memory is not None:
                    os.environ["BUGHUNTER_MEMORY_DIR"] = old_memory
                else:
                    os.environ.pop("BUGHUNTER_MEMORY_DIR", None)
                if old_cbh_home is not None:
                    os.environ["CBH_HOME"] = old_cbh_home
                else:
                    os.environ.pop("CBH_HOME", None)

    def test_memory_dedup_is_atomic_across_processes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            code = (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "from engine import memory; "
                "f={'url':'https://api.example.com/u?id=1','param':'id',"
                "'vuln_class':'idor','severity':'high'}; "
                "print(memory.record_finding('demo','api.example.com',['api'],f,{'reason':'x'}))"
            )
            env = os.environ.copy()
            env["BUGHUNTER_MEMORY_DIR"] = temp_dir
            processes = [subprocess.Popen(
                [sys.executable, "-c", code, str(PLUGIN)], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, env=env,
            ) for _ in range(12)]
            results = [process.communicate(timeout=30) for process in processes]
            self.assertTrue(all(process.returncode == 0 for process in processes), results)
            self.assertEqual(sum(stdout.strip() == "True" for stdout, _ in results), 1)
            rows = (Path(temp_dir) / "findings.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1)

    def test_memory_purge_finds_backup_when_live_file_was_rotated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            live = Path(temp_dir) / "findings.jsonl"
            live.write_text('{"row":1}\n', encoding="utf-8")
            memory.gc("rotate", max_mb=0, root=temp_dir)
            backup = Path(f"{live}.1")
            self.assertTrue(backup.is_file())
            rows = memory.gc("purge-backups", root=temp_dir)
            self.assertFalse(backup.exists())
            self.assertEqual(rows[0]["backups"], 0)

    def test_mock_autopilot_completes_without_network(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            command = [
                sys.executable,
                str(PLUGIN / "scripts/cbh.py"),
                "autopilot",
                "--scope-file", str(PLUGIN / "engine/engagement.example.json"),
                "--base", temp_dir,
                "--mock",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            state_path = Path(temp_dir) / "demo-local/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["phase"], "done")
            self.assertEqual(len(state["surface"]), 3)

    def test_recon_cli_requires_scope_file_before_running(self):
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "scripts/cbh.py"), "recon", "example.com"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--scope-file", completed.stderr)


if __name__ == "__main__":
    unittest.main()
