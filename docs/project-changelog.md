# Project changelog

## 2.1.1 — 2026-09-04

- Released the in-place `v2.1.1` Codex BugHunter patch.
- Synced the manifest, package, runtime, CLI producer string, docs, banner, and
  tests to `2.1.1`.
- Replaced stale fork-owned legacy release URLs with
  `https://git.ot9.me/Adminx/codex-bughunter` while preserving upstream GitHub
  provenance links.
- Tightened PowerShell and POSIX installers to parse Codex JSON, validate the
  exact marketplace root and plugin source, and refresh
  `codex-bughunter@codex-bughunter-local` on repeat install runs.
- Added release-contract coverage for marketplace policy/auth/category, prompt
  limits, canonical URLs, version parity, and installer behavior using a fake
  Codex process boundary.
- Passed 36 unit tests and 33 final release gates covering plugin validation,
  Python compile/package installs, shell syntax, PowerShell parsing, installer
  failure paths, banner validation, secret scanning, and Git cleanliness.
- Independent final review reported no P0/P1/P2 findings. Published `main` and
  annotated `v2.1.1` to the canonical origin.

## 2.1.0 — 2026-09-01

- Converted Claude commands into 15 explicit Codex workflow skills.
- Packaged 83 domain skills in a native Codex plugin and local marketplace.
- Replaced headless Claude dispatch with sandboxed `codex exec` and JSON Schema output.
- Added Windows/POSIX memory locking and explicit UTF-8 persistence.
- Added Codex-only installers, engagement scaffolding, CLI commands, and Burp MCP opt-in.
- Made recon fail closed on written scope, disabled automatic redirects, and
  kept default auth-enforcement probes GET-only.
- Made finding deduplication and ledger maintenance atomic across processes;
  existing MCP entries now fail safely unless replacement is explicit.
- Preserved upstream licensing, content attribution, and source provenance.
- Verified the release build with 17/17 unit tests, Windows and WSL compile/selftest/mock/concurrency/install matrices, and a final `2.1.0` wheel build/import without pycache leakage.
- Independent final review reported no P0/P1/P2 issues.
- Upstream `other/Claude-BugHunter` stayed unchanged at 330 files with hash `79e661c03ff742f15c24cc6246b1c1052b1ef90147b5b5e3011266823e228845`.
- Remote publication of `main` and `v2.1.0` was verified at
  `https://git.ot9.me/Adminx/codex-bughunter.git`.
