# Codex BugHunter repository guidance

This repository is a Codex-only derivative of Claude-BugHunter. Do not edit the
read-only upstream checkout under `other/Claude-BugHunter`.

## Safety invariants

- Security testing requires explicit authorization and a written scope.
- Scope is default-deny; explicit out-of-scope rules always win.
- Model-driven engine phases are opt-in and use the read-only Codex sandbox.
- Burp MCP is opt-in. Never commit local JAR paths, tokens, or target evidence.

## Validation

Run focused unit tests, Python compilation, skill lint, plugin validation, shell
parser checks, and a package build before release. Preserve upstream attribution
and both license families.
