# Contributing

Contributions belong in the local Gitea project. Keep changes scoped, preserve
upstream attribution, and never include target identifiers, credentials,
engagement evidence, or other personal data.

## Skills

- Keep `SKILL.md` frontmatter valid and descriptions at most 1024 characters.
- Add `sources:` metadata and cite durable public references.
- Workflow skills need `agents/openai.yaml` with implicit invocation disabled.
- Do not place machine-specific paths or MCP credentials in the repository.

## Validation

Before proposing a change:

```text
python scripts/lint_skills.py
python -m compileall -q engine cbh scripts
python ../../tests/test_codex_conversion.py
python -m pip wheel --no-deps --wheel-dir dist .
```

Run shell and PowerShell parser checks when their scripts change. Use a focused,
conventional commit message without AI attribution.
