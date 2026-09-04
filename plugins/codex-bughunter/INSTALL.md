# Installation

## Requirements

- Codex CLI 0.145.0 or newer
- Python 3.9 or newer for `cbh` and the optional engine
- Git for marketplace checkouts

## Recommended installer

Run from the repository root for a checkout-backed install that tracks your local
branch:

```powershell
pwsh ./plugins/codex-bughunter/scripts/install.ps1
python -m pip install -e ./plugins/codex-bughunter
```

```sh
sh ./plugins/codex-bughunter/scripts/install.sh
python3 -m pip install -e ./plugins/codex-bughunter
```

The installer registers this repository as marketplace
`codex-bughunter-local`, validates that the configured marketplace root matches
this checkout, then installs or refreshes
`codex-bughunter@codex-bughunter-local`. It does not write to `~/.claude`.

Equivalent manual commands:

```text
codex plugin marketplace add <repository-root> --json
codex plugin add codex-bughunter@codex-bughunter-local --json
```

Restart Codex after installation.

## Update a branch-tracking checkout

After pulling a newer commit into the same checkout, re-run the installer and
refresh the editable package:

```powershell
git pull --ff-only origin main
pwsh ./plugins/codex-bughunter/scripts/install.ps1
python -m pip install -e ./plugins/codex-bughunter
```

```sh
git pull --ff-only origin main
sh ./plugins/codex-bughunter/scripts/install.sh
python3 -m pip install -e ./plugins/codex-bughunter
```

If the marketplace name already exists but points at a different checkout, the
installer stops instead of replacing another source.

## Install a pinned tag

Use a Git-backed marketplace when you want a reviewed immutable tag instead of a
live checkout. These examples use the currently published `v2.1.0` release;
swap in a newer approved tag after it has been published:

```powershell
codex plugin marketplace add `
  https://git.ot9.me/Adminx/codex-bughunter.git --ref v2.1.0 --json
codex plugin add codex-bughunter@codex-bughunter-local --json
python -m pip install `
  "git+https://git.ot9.me/Adminx/codex-bughunter.git@v2.1.0#subdirectory=plugins/codex-bughunter"
```

```sh
codex plugin marketplace add \
  https://git.ot9.me/Adminx/codex-bughunter.git --ref v2.1.0 --json
codex plugin add codex-bughunter@codex-bughunter-local --json
python3 -m pip install \
  "git+https://git.ot9.me/Adminx/codex-bughunter.git@v2.1.0#subdirectory=plugins/codex-bughunter"
```

## Update a branch-tracking Git marketplace

If `codex-bughunter-local` was added from the repository URL without `--ref`,
refresh the marketplace and then reinstall the plugin:

```text
codex plugin marketplace upgrade codex-bughunter-local --json
codex plugin add codex-bughunter@codex-bughunter-local --json
```

## Move or roll back a pinned tag

A marketplace pinned with `--ref v2.1.0` does not move with `upgrade`. To switch
to another approved tag or roll back, remove only this plugin and marketplace,
then re-add the desired ref:

```powershell
codex plugin remove codex-bughunter@codex-bughunter-local --json
codex plugin marketplace remove codex-bughunter-local --json
codex plugin marketplace add `
  https://git.ot9.me/Adminx/codex-bughunter.git --ref v2.1.0 --json
codex plugin add codex-bughunter@codex-bughunter-local --json
python -m pip install `
  "git+https://git.ot9.me/Adminx/codex-bughunter.git@v2.1.0#subdirectory=plugins/codex-bughunter"
```

```sh
codex plugin remove codex-bughunter@codex-bughunter-local --json
codex plugin marketplace remove codex-bughunter-local --json
codex plugin marketplace add \
  https://git.ot9.me/Adminx/codex-bughunter.git --ref v2.1.0 --json
codex plugin add codex-bughunter@codex-bughunter-local --json
python3 -m pip install \
  "git+https://git.ot9.me/Adminx/codex-bughunter.git@v2.1.0#subdirectory=plugins/codex-bughunter"
```

This rollback does not delete engagements or memory under `~/.codex/bughunter/`.

## Burp MCP opt-in

Configure only a transport you control. No default local JAR path is assumed.

```powershell
python ./plugins/codex-bughunter/scripts/setup_harness_mcp.py --jar C:\absolute\burp-mcp.jar
python ./plugins/codex-bughunter/scripts/setup_harness_mcp.py --url http://127.0.0.1:9876/mcp
```

The helper fails safely if that MCP server name already exists. Inspect the
existing entry first; pass `--replace` only when you intentionally want to
remove and recreate that named entry. By default it preserves existing Codex
MCP entries and only touches the named server (`burp` by default).

Use `--dry-run` to inspect commands first.

## Remove

```powershell
pwsh ./plugins/codex-bughunter/scripts/install.ps1 -Uninstall -RemoveMarketplace
```

```sh
sh ./plugins/codex-bughunter/scripts/install.sh --uninstall --remove-marketplace
```

Removing the plugin does not delete engagements or memory under
`~/.codex/bughunter/`.
