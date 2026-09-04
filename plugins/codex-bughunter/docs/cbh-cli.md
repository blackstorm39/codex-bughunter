# `cbh` CLI

`cbh` is the deterministic companion to the Codex plugin. It is useful for
repeatable recon, CI, offline classification, and resumable engine runs.

| Command | Purpose |
|---|---|
| `cbh init` | Create `scope.json` and `AGENTS.md`. |
| `cbh scope` | Apply deny-wins, default-deny scope rules. |
| `cbh recon` | Scope-gated passive discovery and GET-only manifest generation; requires `--scope-file`. |
| `cbh surface` | Rank an existing recon manifest. |
| `cbh classify` | Map a URL to hunt skills and report patterns. |
| `cbh triage` | Apply the deterministic seven-question gate. |
| `cbh report` | Render a platform report template. |
| `cbh autopilot` | Run the portable engagement engine. |
| `cbh memory` | Inspect, rotate, or purge ledger backups. |

Run `cbh <command> --help` for exact arguments. For model judgment, invoke an
explicit plugin workflow such as `$codex-bughunter:workflow-hunt` in Codex.

Recon fails closed without written scope:

```text
cbh recon target.example --scope-file target.example/scope.json
```
