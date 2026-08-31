#!/usr/bin/env bash
# Register Amnesia as an MCP server in the AI clients on this machine.
#
# This is the step that turns Amnesia from an app into memory: once registered,
# Claude Code and Cursor answer from the same beliefs the background pass fills.
# Safe to re-run; each client is checked before it is touched, and every config
# is backed up before it is written.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

echo "==> Repo:   $REPO"
echo "==> Python: $PY"

register() {
  local label="$1" cfg="$2"
  [ -f "$cfg" ] || { echo "==> $label: no config at $cfg, skipped"; return; }
  REPO="$REPO" PY="$PY" CFG="$cfg" LABEL="$label" python3 - <<'PY'
import json, os, shutil, time

cfg, repo, py, label = (os.environ[k] for k in ("CFG", "REPO", "PY", "LABEL"))
with open(cfg, encoding="utf-8") as f:
    data = json.load(f)

servers = data.setdefault("mcpServers", {})
if "amnesia" in servers:
    print(f"==> {label}: already registered")
else:
    shutil.copy(cfg, f"{cfg}.bak.{int(time.time())}")
    servers["amnesia"] = {
        "command": py,
        "args": ["-m", "amnesia.mcp.server"],
        "env": {"PYTHONPATH": repo},
    }
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"==> {label}: registered (backup saved)")
PY
}

register "Claude Code"    "$HOME/.claude.json"
register "Claude Desktop" "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
register "Cursor"         "$HOME/.cursor/mcp.json"

echo
echo "==> Restart the client, then ask it: \"what do you know about how I work?\""
