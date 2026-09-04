---
name: workflow-recon
description: "Explicit Codex workflow. Build a scope-filtered recon manifest from passive subdomain discovery, DNS resolution, and GET-only HTTP probes. Requires a written scope JSON. Invoke only as $codex-bughunter:workflow-recon."
user-invocable: true
disable-model-invocation: false
sources: upstream-command, operator_experience
---

# Workflow: recon

## Codex invocation contract

This workflow is explicit-only. Treat text after `$codex-bughunter:workflow-recon` as its arguments. Resolve bundled helpers relative to this installed skill (plugin root is two directories above `skills/workflow-recon`), while writing engagement artifacts only in the user's current workspace.

Require both a target and `--scope-file <scope.json>`. Do not infer authorization from the target name, a prior URL, or public reachability. The scope file is deny-wins and default-deny.

## Usage

```text
$codex-bughunter:workflow-recon target.example --scope-file ./scope.json
$codex-bughunter:workflow-recon target.example --scope-file ./scope.json --burp
```

## Procedure

1. Resolve the plugin root from this skill location.
2. Confirm the scope file exists and records the requested target as in scope.
3. Run the deterministic CLI:

   ```bash
   python <plugin-root>/scripts/cbh.py recon target.example --scope-file ./scope.json
   ```

   Forward only supported operator arguments such as `--out`, `--burp`, or `--proxy`.
4. Read `recon/<target>/manifest.json`. Treat only its `assets` and `ranked_surface` entries as eligible targets; the CLI has already removed out-of-scope discoveries.
5. Summarize live hosts, technology hints, and ranked attack-surface candidates. Preserve the manifest as the recon-to-hunt handoff.
6. Suggest `$codex-bughunter:workflow-surface <target>` for prioritization or `$codex-bughunter:workflow-hunt <target>` for active testing.

## Safety invariants

- Never DNS-resolve, HTTP-probe, crawl, scan, or invoke nuclei against an unfiltered discovery list.
- Never follow a redirect automatically. Validate the redirect destination against the same scope before a new request.
- Default network behavior is GET-only and non-destructive. POST, PUT, PATCH, DELETE, credential use, brute force, nuclei templates with side effects, and other intrusive actions require explicit authorization.
- Passive third-party data sources may reveal out-of-scope names. Record the count, discard those names, and do not contact them.
- If the scope file is missing, invalid, or excludes the target, stop without network access.

## Output

The CLI writes a scoped engagement artifact directory containing:

```text
recon/<target>/
  subdomains.txt
  resolved.txt
  live-hosts.json
  RECON_SUMMARY.md
  manifest.json
```

The manifest is the authoritative downstream input. Do not rebuild a target list from raw passive-source output.
