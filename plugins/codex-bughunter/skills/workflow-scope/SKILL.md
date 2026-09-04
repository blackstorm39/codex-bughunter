---
name: workflow-scope
description: "Explicit Codex workflow. Mandatory pre-flight scope check — verify an asset is in scope BEFORE any HTTP touch. Deterministic (deny-wins, default-deny) via engine/scope.py against the engagement's scope.md. Blocks out-of-scope testing. Invoke only as $codex-bughunter:workflow-scope."
user-invocable: true
disable-model-invocation: false
sources: upstream-command, operator_experience
---

# Workflow: scope

## Codex invocation contract

This workflow is explicit-only. Treat text after `$codex-bughunter:workflow-scope` as its arguments. Resolve bundled helpers relative to this installed skill (plugin root is two directories above `skills/workflow-scope`), while writing engagement artifacts only in the user's current workspace. Confirm authorization and enforce recorded scope before any active request.

Bare host patterns authorize that exact host only. Use an explicit `*.` pattern
to authorize descendants. Malformed regex or CIDR rules invalidate the scope
file; never ignore a broken deny rule.

The mandatory pre-flight gate. Verify a host or URL is in scope **before** any
active testing. Scope is enforced in **code** (`engine/scope.py`), not by LLM
judgment — deny wins, default deny.

## What This Does

1. Loads in-scope / out-of-scope patterns from the engagement's `scope.md`
   (the `hunt` scaffold creates it) or from inline patterns.
2. Checks each asset deterministically with `engine/scope.py`:
   - apex `acme.com` → the apex **and** any subdomain
   - `*.acme.com` → any subdomain (NOT the bare apex)
   - `api.acme.com` → that exact host
   - `10.0.0.0/8` → any IP in the CIDR
   - `re:^lab[0-9]+\.acme\.io$` → explicit regex (prefix `re:`)
3. Prints `IN-SCOPE` / `OUT-OF-SCOPE <reason>` and exits non-zero if any asset
   is out of scope — so it can gate automation.

## Usage

```
$codex-bughunter:workflow-scope api.acme.com
$codex-bughunter:workflow-scope api.acme.com staging.acme.io admin.acme.com
```

Under the hood, run the deterministic checker directly:

```bash
# Against the engagement scope.md (preferred — fill scope.md from the program page first)
python3 engine/scope.py api.acme.com --md ~/Targets/acme/scope.md

# Or with inline patterns (repeat --in-scope / --out-of-scope per pattern)
python3 engine/scope.py api.acme.com evil.com \
  --in-scope acme.com --in-scope '*.acme.io' --out-of-scope admin.acme.com
```

## Rules

- **Run this before any HTTP touch.** An `OUT-OF-SCOPE` result is a hard stop —
  do not probe the asset.
- If `scope.md` is still the empty template (`(paste ... here)` placeholders),
  fill it from the program page first; an empty in-scope list = default-deny =
  everything rejected, which is the safe default.
- Deny wins: if an asset matches both an in-scope and an out-of-scope rule, it is
  out of scope.
