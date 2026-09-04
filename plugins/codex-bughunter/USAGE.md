# Usage

Only test assets covered by written authorization. Use
`$codex-bughunter:workflow-scope` before active testing and keep an explicit
deny list.

## Workflows

All workflows require explicit invocation:

- `workflow-scope` — parse and verify authorized scope.
- `workflow-recon` — map reachable attack surface.
- `workflow-surface` — rank and present a recon manifest.
- `workflow-hunt` — route a target through relevant hunt skills.
- `workflow-autopilot` — coordinate a resumable engagement.
- `workflow-triage` — apply the fast validation gate.
- `workflow-validate` — perform the full validation gate.
- `workflow-report` — draft a submission-ready report.
- `workflow-chain` — evaluate one exploit chain.
- `workflow-intel` — collect authorized target intelligence.
- `workflow-token-scan` — inspect supplied token material safely.
- `workflow-web3-audit` — route an authorized web3 assessment.
- `workflow-remember` — write a confirmed result to memory.
- `workflow-pickup` — resume from saved engagement state.
- `workflow-memory-gc` — inspect, rotate, or purge memory backups.

Example:

```text
$codex-bughunter:workflow-hunt https://api.target.example
```

Domain skills can also be named directly, such as
`$codex-bughunter:hunt-idor`, when the vulnerability class is already known.

## Deterministic CLI

```text
cbh init target.example --in-scope target.example --in-scope "*.target.example" \
  --out-of-scope admin.target.example
cbh scope https://api.target.example --scope-file target.example/scope.json
cbh recon target.example --scope-file target.example/scope.json
cbh classify "https://api.target.example/users?id=7"
cbh triage finding.md
cbh report finding.md --platform bugcrowd --out report.md
```

The engine defaults to deterministic `recon,rank,map` and stops before active
model-driven testing:

```text
cbh autopilot --scope-file target.example/scope.json
cbh autopilot --scope-file target.example/scope.json --mock
```

`--hunt` explicitly enables the model-driven hunt and validation phases. The
adapter uses `codex exec --sandbox read-only`; `--allow-intrusive` changes the
rules of engagement but does not disable the Codex sandbox.

Memory defaults to `~/.codex/bughunter/memory` and can be redirected with
`BUGHUNTER_MEMORY_DIR` or `CBH_HOME`:

```text
cbh memory --action report
cbh memory --host api.target.example
```
