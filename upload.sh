#!/usr/bin/env bash
# Upload blueprint.json to Make.com, injecting API keys from .env at upload time.
# Usage:  ./upload.sh           -> updates scenario $MAKE_SCENARIO_ID in place
#         ./upload.sh new       -> creates a new scenario
set -euo pipefail
cd "$(dirname "$0")"

set -a; source .env; set +a

: "${MAKE_API_TOKEN:?}" "${MAKE_TEAM_ID:?}" "${MAKE_REGION:=us2}"

# Inject secrets into a transient copy of the blueprint
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

sed \
  -e "s|__ELEVENLABS_API_KEY__|${ELEVENLABS_API_KEY:-MISSING_ELEVENLABS_KEY}|g" \
  -e "s|__JSON2VIDEO_API_KEY__|${JSON2VIDEO_API_KEY:-MISSING_JSON2VIDEO_KEY}|g" \
  -e "s|__TELEGRAM_BOT_TOKEN__|${TELEGRAM_BOT_TOKEN:-MISSING_TELEGRAM_TOKEN}|g" \
  blueprint.json > "$TMP"

# Build the API payload: Make expects {blueprint: "<stringified JSON>", ...}
# POST (create) requires teamId; PATCH (update) rejects it.
MODE="${1:-update}"
BASE="https://${MAKE_REGION}.make.com/api/v2"

if [[ "$MODE" == "new" ]]; then
  PAYLOAD=$(python3 - "$TMP" "$MAKE_TEAM_ID" <<'PY'
import json, sys
bp = json.load(open(sys.argv[1]))
print(json.dumps({
    "name": bp["name"],
    "teamId": int(sys.argv[2]),
    "scheduling": json.dumps({"type": "indefinitely", "interval": 900}),
    "blueprint": json.dumps(bp),
}))
PY
)
  echo "Creating NEW scenario..."
  RESP=$(curl -sS -X POST "$BASE/scenarios?confirmed=true" \
    -H "Authorization: Token $MAKE_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
else
  : "${MAKE_SCENARIO_ID:?}"
  PAYLOAD=$(python3 - "$TMP" <<'PY'
import json, sys
bp = json.load(open(sys.argv[1]))
print(json.dumps({
    "name": bp["name"],
    "scheduling": json.dumps({"type": "indefinitely", "interval": 900}),
    "blueprint": json.dumps(bp),
}))
PY
)
  echo "Updating scenario $MAKE_SCENARIO_ID..."
  RESP=$(curl -sS -X PATCH "$BASE/scenarios/$MAKE_SCENARIO_ID?confirmed=true" \
    -H "Authorization: Token $MAKE_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
fi

echo "$RESP" | python3 -m json.tool || echo "$RESP"
