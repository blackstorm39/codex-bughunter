#!/usr/bin/env sh
set -eu

plugin_name="codex-bughunter"
marketplace_name="codex-bughunter-local"
plugin_id="${plugin_name}@${marketplace_name}"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
plugin_root=$(dirname "$script_dir")
repo_root=$(dirname "$(dirname "$plugin_root")")
manifest="$repo_root/.agents/plugins/marketplace.json"
uninstall=0
remove_marketplace=0
burp_jar=""
burp_url=""
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/codex-bughunter-install.XXXXXX")
marketplace_json="$scratch_dir/marketplaces.json"
installed_json="$scratch_dir/plugins-installed.json"
available_json="$scratch_dir/plugins-available.json"

cleanup() {
  rm -rf "$scratch_dir"
}

trap cleanup EXIT HUP INT TERM

usage() {
  printf '%s\n' \
    'Install Codex BugHunter from this checkout:' \
    '  sh ./plugins/codex-bughunter/scripts/install.sh' \
    '' \
    'Options:' \
    '  --uninstall             remove the plugin' \
    '  --remove-marketplace    also remove the local marketplace' \
    '  --burp-jar PATH         opt in to a local Burp MCP JAR' \
    '  --burp-url URL          opt in to a running Burp MCP HTTP endpoint' \
    '  --help                  show this help'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --uninstall) uninstall=1 ;;
    --remove-marketplace) remove_marketplace=1 ;;
    --burp-jar) shift; burp_jar=${1:?missing path for --burp-jar} ;;
    --burp-url) shift; burp_url=${1:?missing URL for --burp-url} ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[ -z "$burp_jar" ] || [ -z "$burp_url" ] || { printf 'Choose one Burp transport.\n' >&2; exit 2; }
command -v codex >/dev/null 2>&1 || { printf 'Codex CLI is required.\n' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { printf 'Python 3 is required.\n' >&2; exit 1; }
[ -f "$manifest" ] || { printf 'Marketplace manifest not found: %s\n' "$manifest" >&2; exit 1; }

expected_marketplace_root=$(python3 -c 'import os, sys; path = sys.argv[1]; print(os.path.normcase(os.path.abspath(path)))' "$repo_root")
expected_plugin_root=$(python3 -c 'import os, sys; path = sys.argv[1]; print(os.path.normcase(os.path.abspath(path)))' "$plugin_root")

capture_codex_json() {
  output_file=$1
  shift
  codex "$@" >"$output_file" || return $?
  python3 - "$output_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = handle.read()
if not payload.strip():
    print("Codex command returned empty JSON output.", file=sys.stderr)
    raise SystemExit(4)
parsed = json.loads(payload)
if not isinstance(parsed, dict):
    print("Codex command returned a non-object JSON payload.", file=sys.stderr)
    raise SystemExit(4)
PY
}

assert_marketplace_matches() {
  python3 - "$marketplace_json" "$marketplace_name" "$expected_marketplace_root" <<'PY'
import json
import os
import sys

json_path, marketplace_name, expected_root = sys.argv[1:4]
with open(json_path, encoding="utf-8") as handle:
    payload = json.load(handle)
marketplaces = payload.get("marketplaces")
if not isinstance(marketplaces, list):
    print("Marketplace list omitted the required marketplaces array.", file=sys.stderr)
    raise SystemExit(4)
matches = [item for item in marketplaces if isinstance(item, dict) and item.get("name") == marketplace_name]
if len(matches) > 1:
    print(f"Multiple marketplaces named {marketplace_name} are configured.", file=sys.stderr)
    raise SystemExit(3)
if not matches:
    raise SystemExit(10)
root = matches[0].get("root")
if not root:
    print(f"Marketplace {marketplace_name} does not report a root.", file=sys.stderr)
    raise SystemExit(4)
if root.startswith("\\\\?\\UNC\\"):
    root = "\\\\" + root[8:]
elif root.startswith("\\\\?\\"):
    root = root[4:]
actual_root = os.path.normcase(os.path.abspath(root))
if actual_root != expected_root:
    print(
        f"Marketplace {marketplace_name} already points to {actual_root}, expected {expected_root}.",
        file=sys.stderr,
    )
    raise SystemExit(4)
PY
}

assert_plugin_matches() {
  python3 - "$1" "$2" "$plugin_id" "$expected_plugin_root" "$expected_marketplace_root" <<'PY'
import json
import os
import sys

json_path, record_set, plugin_id, expected_plugin_root, expected_marketplace_root = sys.argv[1:6]
with open(json_path, encoding="utf-8") as handle:
    payload = json.load(handle)
records = payload.get(record_set)
if not isinstance(records, list):
    print(f"Plugin list omitted the required {record_set} array.", file=sys.stderr)
    raise SystemExit(4)
matches = [item for item in records if isinstance(item, dict) and item.get("pluginId") == plugin_id]
if len(matches) > 1:
    print(f"Multiple plugin records matched {plugin_id}.", file=sys.stderr)
    raise SystemExit(3)
if not matches:
    raise SystemExit(10)
source = matches[0].get("source")
if not isinstance(source, dict):
    print(f"Plugin record for {plugin_id} is missing a valid source object.", file=sys.stderr)
    raise SystemExit(4)
path = source.get("path")
if not path:
    print(f"Plugin {plugin_id} is missing a source path.", file=sys.stderr)
    raise SystemExit(4)
if path.startswith("\\\\?\\UNC\\"):
    path = "\\\\" + path[8:]
elif path.startswith("\\\\?\\"):
    path = path[4:]
actual_source = os.path.normcase(os.path.abspath(path))
if actual_source != expected_plugin_root:
    print(
        f"Plugin {plugin_id} is surfaced from {actual_source}, expected {expected_plugin_root}.",
        file=sys.stderr,
    )
    raise SystemExit(4)
marketplace_source = matches[0].get("marketplaceSource")
if isinstance(marketplace_source, dict) and marketplace_source.get("sourceType") == "local":
    source_root = marketplace_source.get("source")
    if not source_root:
        print(f"Plugin {plugin_id} is missing a marketplace source path.", file=sys.stderr)
        raise SystemExit(4)
    if source_root.startswith("\\\\?\\UNC\\"):
        source_root = "\\\\" + source_root[8:]
    elif source_root.startswith("\\\\?\\"):
        source_root = source_root[4:]
    actual_marketplace_root = os.path.normcase(os.path.abspath(source_root))
    if actual_marketplace_root != expected_marketplace_root:
        print(
            f"Plugin {plugin_id} is linked to marketplace root {actual_marketplace_root}, expected {expected_marketplace_root}.",
            file=sys.stderr,
        )
        raise SystemExit(4)
PY
}

match_or_missing() {
  status=0
  "$@" || status=$?
  if [ "$status" -eq 0 ]; then
    return 0
  fi
  if [ "$status" -eq 10 ]; then
    return 1
  fi
  return $status
}

marketplace_exists() {
  capture_codex_json "$marketplace_json" plugin marketplace list --json || return $?
  match_or_missing assert_marketplace_matches || return $?
}

plugin_record_exists() {
  record_set=$1
  output_file=$2
  shift 2
  capture_codex_json "$output_file" "$@" || return $?
  match_or_missing assert_plugin_matches "$output_file" "$record_set" || return $?
}

if [ "$uninstall" -eq 1 ]; then
  installed_status=0
  plugin_record_exists installed "$installed_json" plugin list --json || installed_status=$?
  if [ "$installed_status" -eq 0 ]; then
    codex plugin remove "$plugin_id" --json
  elif [ "$installed_status" -eq 1 ]; then
    printf 'Codex BugHunter is not installed.\n'
  else
    exit "$installed_status"
  fi
  if [ "$remove_marketplace" -eq 1 ]; then
    marketplace_status=0
    marketplace_exists || marketplace_status=$?
    if [ "$marketplace_status" -eq 0 ]; then
      codex plugin marketplace remove "$marketplace_name" --json
    elif [ "$marketplace_status" -ne 1 ]; then
      exit "$marketplace_status"
    fi
  fi
  exit 0
fi

marketplace_status=0
marketplace_exists || marketplace_status=$?
if [ "$marketplace_status" -eq 1 ]; then
  codex plugin marketplace add "$repo_root" --json
elif [ "$marketplace_status" -ne 0 ]; then
  exit "$marketplace_status"
fi

available_status=0
plugin_record_exists available "$available_json" plugin list --available --json || available_status=$?
if [ "$available_status" -gt 1 ]; then
  exit "$available_status"
fi

installed_status=0
plugin_record_exists installed "$installed_json" plugin list --json || installed_status=$?
if [ "$installed_status" -gt 1 ]; then
  exit "$installed_status"
fi

if [ "$available_status" -eq 1 ] && [ "$installed_status" -eq 1 ]; then
  printf 'Plugin %s was not found in the configured marketplace or installed set.\n' "$plugin_id" >&2
  exit 4
fi

codex plugin add "$plugin_id" --json

if [ -n "$burp_jar" ]; then
  python3 "$script_dir/setup_harness_mcp.py" --jar "$burp_jar"
elif [ -n "$burp_url" ]; then
  python3 "$script_dir/setup_harness_mcp.py" --url "$burp_url"
fi

printf 'Installed. Restart Codex, then invoke $codex-bughunter:workflow-hunt explicitly.\n'
