# Development roadmap

## 2.1.1 — Patch release

- [x] Sync the live plugin, package, CLI, docs, banner, and tests to `2.1.1`.
- [x] Replace stale fork-owned URLs with `https://git.ot9.me/Adminx/codex-bughunter`.
- [x] Make repeat installer runs validate the exact marketplace/plugin source and refresh with `codex plugin add`.
- [x] Pass isolated validation, install smoke, review, and publication gates.

Release status: `main` and annotated `v2.1.1` are published at
`https://git.ot9.me/Adminx/codex-bughunter.git`.

## 2.1.0 — Codex conversion

- [x] Create local Codex marketplace and plugin manifest.
- [x] Import 83 upstream domain skills.
- [x] Convert 15 commands to explicit workflow skills.
- [x] Replace the model adapter with `codex exec`.
- [x] Port memory locking and UTF-8 state to Windows/POSIX.
- [x] Add Codex-native installers, CLI entry points, and opt-in Burp MCP setup.
- [x] Complete independent test and code-review gates.
- [x] Prepare one focused `v2.1.0` release commit and annotated tag.
- [x] Push `main` and `v2.1.0` to the canonical origin.

Release status: `main` and annotated `v2.1.0` are published at
`https://git.ot9.me/Adminx/codex-bughunter.git`.

## Later

- Validate live authorized engagements across Windows and Linux.
- Add compatibility tests when Codex plugin or MCP contracts change.
