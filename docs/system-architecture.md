# System architecture

## Boundaries

- The root marketplace publishes one plugin: `codex-bughunter`.
- `skills/` contains 83 domain skills and 15 converted workflow skills.
- Workflow skills have `agents/openai.yaml` and disable implicit invocation.
- `cbh` owns deterministic operator commands.
- `engine` owns scope, state, recon, mapping, optional model dispatch, and memory.
- Scope rules are exact-host by default; descendant coverage requires explicit
  `*.` wildcards, and malformed scope rules fail closed during load.
- `recon` uses scope-gated discovery, GET-only auth sweeps by default, no
  automatic redirects, and a Katana live crawl constrained to FQDN results.
- `memory` is a locked JSONL ledger with atomic append / rotate behavior across
  Windows and POSIX.
- Burp is an optional Codex MCP transport configured by the operator.

## Execution

The engine runs `scope → recon → rank → map` by default. The `--hunt` switch
adds `hunt → validate → report`. Scope is checked before dispatch. Model calls
use `codex exec` with prompts on stdin, JSON Schema output, timeouts, and the
read-only sandbox. Seeds are rejected before state creation or network access,
recon requires written scope, redirects are returned without being followed,
and the default OpenAPI enforcement sweep sends GET requests only.

Engagement state and cross-engagement memory remain separate. State is scoped
to a run; memory lives under `~/.codex/bughunter/memory` unless overridden.
JSONL finding deduplication and maintenance use one cross-process transaction
lock on Windows and POSIX.
