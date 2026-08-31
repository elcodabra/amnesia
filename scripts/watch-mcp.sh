#!/usr/bin/env bash
# Watch which AI client is calling Amnesia, and what it asks for.
#
# Written for the demo: a remote connector is invisible from the outside, so
# this is the window that proves ChatGPT is really talking to the service
# rather than answering from its own context.
#
# Usage:
#   ./scripts/watch-mcp.sh          # follow live
#   ./scripts/watch-mcp.sh 60       # last 60 minutes, then follow
set -uo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-amnesia-agent-87425}"
SERVICE="${AMNESIA_SERVICE:-amnesia}"
GCLOUD="${GCLOUD_BIN:-$HOME/google-cloud-sdk/bin/gcloud}"
command -v "$GCLOUD" >/dev/null 2>&1 || GCLOUD=gcloud
SINCE="${1:-10}"

FILTER="resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE}"

echo "==> Watching MCP traffic for ${SERVICE} (${PROJECT})"
echo "==> Showing the last ${SINCE} minutes, then following live."
echo

# History first, oldest last so it reads top to bottom like the live tail does.
"$GCLOUD" logging read "$FILTER AND textPayload:\"[amnesia] mcp\"" \
  --project "$PROJECT" --freshness "${SINCE}m" --limit 40 \
  --format='value(timestamp,textPayload)' 2>/dev/null \
  | tail -r 2>/dev/null || true

echo
echo "==> Live (Ctrl-C to stop)"

# tail streams, but only prints new entries, which is why the history above is
# fetched separately rather than relying on it.
"$GCLOUD" beta logging tail "$FILTER" \
  --project "$PROJECT" \
  --format='value(textPayload)' 2>/dev/null \
  | grep --line-buffered -E "\[amnesia\]|POST /mcp" \
  | while IFS= read -r line; do
      # Colour the two things worth seeing at a glance during a recording.
      case "$line" in
        *"mcp connected"*) printf '\033[92m%s  %s\033[0m\n' "$(date +%H:%M:%S)" "$line" ;;
        *"mcp tool="*)     printf '\033[96m%s  %s\033[0m\n' "$(date +%H:%M:%S)" "$line" ;;
        *)                 printf '%s  %s\n' "$(date +%H:%M:%S)" "$line" ;;
      esac
    done
