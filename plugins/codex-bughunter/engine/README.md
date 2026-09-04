# Portable engagement engine

The engine enforces scope in code, persists state after every phase, and uses a
model only for opt-in hunt and validation.

```text
python -m engine.engine --scope engine/engagement.example.json --mock
python -m engine.engine --scope scope.json
python -m engine.engine --scope scope.json --hunt
```

Default phases are `recon,rank,map`. `--hunt` adds hunt, validation, and report.
The Codex adapter passes prompts over stdin, requests JSON Schema output, uses
an argument array, and defaults to the read-only sandbox.

State defaults to `~/.bughunter-engagements`; the `cbh autopilot` wrapper uses
`~/.codex/bughunter/engagements`. Cross-engagement memory defaults to
`~/.codex/bughunter/memory`.

Key modules:

- `scope.py` — default-deny host and CIDR matching.
- `recon.py` and `osint.py` — deterministic discovery.
- `skill_map.py` — maps surface items to installed plugin skills.
- `agent.py` — `codex exec` subprocess adapter.
- `memory.py` — locked JSONL ledger on Windows and POSIX.
- `state.py` — UTF-8 resumable state, evidence, maps, and reports.
