---
name: workflow-memory-gc
description: "Explicit Codex workflow. Inspect or rotate the autopilot ledger JSONL files (findings.jsonl, negatives.jsonl). Caps file size and keeps N rotated backups so memory does not grow unbounded. Invoke only as $codex-bughunter:workflow-memory-gc."
user-invocable: true
disable-model-invocation: false
sources: upstream-command, operator_experience
---

# Workflow: memory-gc

## Codex invocation contract

This workflow is explicit-only. Treat text after `$codex-bughunter:workflow-memory-gc` as its arguments. Resolve bundled helpers relative to this installed skill (plugin root is two directories above `skills/workflow-memory-gc`), while writing engagement artifacts only in the user's current workspace. Confirm authorization and enforce recorded scope before any active request.

Garbage-collect the autopilot ledger (`~/.codex/bughunter/memory/`). Reports current sizes, rotates oversized files past a configurable cap, or purges old backups.

## Usage

```
$codex-bughunter:workflow-memory-gc                       # report only
$codex-bughunter:workflow-memory-gc --rotate              # rotate files above 10 MB (default cap)
$codex-bughunter:workflow-memory-gc --rotate --max-mb 5   # custom cap
$codex-bughunter:workflow-memory-gc --purge-backups       # delete all .1/.2/.3 backups
$codex-bughunter:workflow-memory-gc --dir <path>          # scan a non-default ledger dir
```

## Implementation

The agent shells out to, from the repo root:

```bash
python3 engine/memory.py --gc [--rotate] [--purge-backups] [--dir PATH] [--max-mb N]
```

## Defaults

- **Rotation cap:** 10 MB per file · **Backups kept:** 3 (`<file>.1` newest → `<file>.3` oldest)
- **Scope:** every `*.jsonl` under the ledger dir (`findings.jsonl`, `negatives.jsonl`)

Rotation also fires automatically on append inside the ledger writer, so files stay bounded without any session-end hook.
