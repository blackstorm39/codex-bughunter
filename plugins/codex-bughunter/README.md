# Codex BugHunter plugin

![Codex BugHunter banner](assets/banner-codex.png)

Codex-native security research workflows derived from Claude-BugHunter. The
plugin contains 83 domain skills and 15 explicit workflow skills. Model-driven
engine phases use `codex exec`; deterministic phases remain offline and
resumable.

## Start

From the repository root:

```powershell
pwsh ./plugins/codex-bughunter/scripts/install.ps1
python -m pip install -e ./plugins/codex-bughunter
```

Restart Codex and invoke a workflow by its full name:

```text
$codex-bughunter:workflow-hunt https://target.example
```

For a pinned tag install, branch-tracking updates, or rollback between published
tags, use the flows in [INSTALL.md](INSTALL.md).

Workflow skills are not invoked implicitly. This prevents a broad security
workflow from starting without the operator's explicit choice.

## Components

- `skills/` — reusable methodology and `workflow-*` entry points.
- `engine/` — scope-safe orchestration and the `codex exec` adapter.
- `cbh/` — deterministic terminal companion.
- `scripts/` — Codex installer, engagement scaffold, and optional Burp MCP setup.
- `docs/disclosed-reports/` — upstream pattern library.

Read [INSTALL.md](INSTALL.md), [USAGE.md](USAGE.md), and
[docs/cbh-cli.md](docs/cbh-cli.md). Attribution is recorded in [UPSTREAM.md](UPSTREAM.md).
