# Code standards

- Keep scope enforcement deterministic, deny-wins, and default-deny.
- Treat bare hosts as exact matches; descendants require an explicit `*.` wildcard.
- Reject malformed regex and CIDR rules at load time so bad scope files fail closed.
- Scope-check every seed and redirect destination before any HTTP request; never
  follow redirects until the destination has passed the same scope check.
- `cbh recon` requires `--scope-file`; the live crawl stays scoped and FQDN-limited.
- Keep the default auth sweep GET-only; state-changing methods stay behind an
  explicit intrusive opt-in.
- Use atomic replacement or locked append for state files and memory ledgers.
- Keep the Burp MCP helper opt-in: preserve existing entries by default and
  replace only the named server when `--replace` is passed.
- Use Codex-only install paths; do not write to `~/.claude`.
- Pass subprocess arguments as arrays; never interpolate model prompts into a shell.
- Keep model-driven operations opt-in and retain the read-only sandbox default.
- Validate every seed and discovered host before DNS or HTTP.
- Support Windows and POSIX with Python standard-library primitives.
- Preserve upstream attribution and do not edit `other/Claude-BugHunter`.
- Run focused tests, plugin validation, skill lint, compile checks, and package build.
