---
name: workflow-pickup
description: "Explicit Codex workflow. Pick up a previous hunt on a target — shows hunt history and untested surface from the autopilot ledger. Invoke only as $codex-bughunter:workflow-pickup."
user-invocable: true
disable-model-invocation: false
sources: upstream-command, operator_experience
---

# Workflow: pickup

## Codex invocation contract

This workflow is explicit-only. Treat text after `$codex-bughunter:workflow-pickup` as its arguments. Resolve bundled helpers relative to this installed skill (plugin root is two directories above `skills/workflow-pickup`), while writing engagement artifacts only in the user's current workspace. Confirm authorization and enforce recorded scope before any active request.

Pick up where you left off on a target.

> **Renamed from `/resume`** — `/resume` is a reserved Codex command.

## What This Does

1. Reads the target rollup from `~/.codex/bughunter/memory/targets/<host>.json`.
2. Shows hunt history (sessions, last seen, tech stack).
3. Lists confirmed findings and the endpoints already tested.

## Usage

```
$codex-bughunter:workflow-pickup target.com
```

## Implementation

The agent reads the rollup directly:

```bash
python3 -c "import sys; sys.path.insert(0,'engine'); import memory, json; print(json.dumps(memory.rollup('target.com'), indent=2))"
```

## If No Previous Hunt

```
No ledger data for target.com. Run $codex-bughunter:workflow-recon then $codex-bughunter:workflow-autopilot target.com first.
```
