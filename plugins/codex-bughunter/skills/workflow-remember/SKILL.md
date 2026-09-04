---
name: workflow-remember
description: "Explicit Codex workflow. Optional manual note on a target or the last confirmed finding. Capture is automatic during autopilot; this is for extra context. Invoke only as $codex-bughunter:workflow-remember."
user-invocable: true
disable-model-invocation: false
sources: upstream-command, operator_experience
---

# Workflow: remember

## Codex invocation contract

This workflow is explicit-only. Treat text after `$codex-bughunter:workflow-remember` as its arguments. Resolve bundled helpers relative to this installed skill (plugin root is two directories above `skills/workflow-remember`), while writing engagement artifacts only in the user's current workspace. Confirm authorization and enforce recorded scope before any active request.

> **Capture is automatic.** During an engine/autopilot run, every confirmed finding is
> written to the ledger (`~/.codex/bughunter/memory/findings.jsonl`) with no action from you.
> `$codex-bughunter:workflow-remember` is only for adding an **optional manual note** — a technique detail or
> follow-up idea — that the automatic capture would not include.

## Usage

```
$codex-bughunter:workflow-remember   # then describe the note; it is appended to the target's rollup
```

## What It Is Not

This is no longer the primary way findings enter memory — the engine captures those
deterministically. Use it sparingly for human context.
