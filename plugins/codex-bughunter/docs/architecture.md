# Codex plugin architecture

Codex loads this repository through `.agents/plugins/marketplace.json`. The
plugin manifest points to `skills/`, where 83 domain skills and 15 `workflow-*`
entry points live.

Workflow agents set `allow_implicit_invocation: false`. The operator must name a
workflow, while narrowly described domain skills remain available for normal
skill routing.

The deterministic engine owns scope, state, discovery, prioritization, and
report persistence. Only hunt and validation dispatch model work. Those calls
use `codex exec`, prompts on stdin, a read-only sandbox, timeouts, and JSON
Schema contracts.

Burp is outside the plugin boundary until an operator explicitly registers a
Codex MCP endpoint or stdio command. No machine-specific path is shipped.
