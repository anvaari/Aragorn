#!/usr/bin/env bash
# Aragorn driver: launch the FastAPI server, smoke-test it, stop it.
#
# Usage:
#   smoke.sh          # side-effect-free checks (auth, validation, schema)
#   smoke.sh --e2e    # additionally sends ONE real, self-deleting test event
#                     # through Telegram + SQLite (posts to the PROD channel
#                     # briefly, then deletes the message and the DB row)
#   PORT=8123 smoke.sh
#
# Must be runnable from anywhere; it cds to the repo root itself because
# the server reads .env from its CWD and uses absolute imports off app/.
set -u
PATH="/usr/sbin:/sbin:$PATH"   # macOS keeps lsof in /usr/sbin, often missing from non-interactive PATHs
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8123}"
BASE="http://127.0.0.1:${PORT}"
LOG="${TMPDIR:-/tmp}/aragorn-smoke-server.log"
FAILS=0
SERVER_PID=""

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
if [ -x ".venv/bin/fastapi" ]; then FASTAPI=".venv/bin/fastapi"; else FASTAPI="fastapi"; fi

env_key() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | xargs; }

check() { # name expected actual
  if [ "$2" = "$3" ]; then echo "PASS: $1 ($3)"; else echo "FAIL: $1 (expected $2, got $3)"; FAILS=$((FAILS+1)); fi
}

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null
  fi
  lsof -ti ":${PORT}" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null
}
trap cleanup EXIT

if ! command -v curl >/dev/null || ! command -v sqlite3 >/dev/null || ! command -v lsof >/dev/null; then
  echo "Needs curl, sqlite3, lsof on PATH"; exit 2
fi

echo "== launching server on :$PORT (log: $LOG) =="
"$FASTAPI" run app/main.py --port "$PORT" >"$LOG" 2>&1 &
SERVER_PID=$!

UP=0
for _ in $(seq 1 30); do
  curl -sf "$BASE/openapi.json" -o /dev/null 2>/dev/null && { UP=1; break; }
  sleep 1
done
if [ "$UP" -ne 1 ]; then
  echo "FAIL: server did not come up in 30s; last log lines:"; tail -20 "$LOG"; exit 1
fi
echo "PASS: server up after <30s"

echo "== schema =="
"$PY" - "$BASE" <<'EOF'
import json, sys, urllib.request
d = json.load(urllib.request.urlopen(f"{sys.argv[1]}/openapi.json"))
paths = sorted(f"{m.upper()} {p}" for p, ms in d["paths"].items() for m in ms)
expected = ["POST /api/v1/events/ig_event", "POST /api/v1/events/image_event", "POST /api/v1/events/manual_event"]
ok = d["info"]["title"].startswith("Aragorn") and paths == expected
print(("PASS: " if ok else "FAIL: ") + f"openapi title={d['info']['title']!r} paths={paths}")
sys.exit(0 if ok else 1)
EOF
[ $? -eq 0 ] || FAILS=$((FAILS+1))

echo "== auth & validation (no external calls are triggered) =="
code() { curl -s -o /tmp/aragorn-smoke-body -w '%{http_code}' "$@"; }

check "GET / is 404 (no root route)" "404" "$(code "$BASE/")"
check "ig_event no auth -> 403" "403" "$(code -X POST "$BASE/api/v1/events/ig_event")"
check "ig_event wrong token -> 403" "403" "$(code -X POST -H 'Authorization: Bearer wrong' "$BASE/api/v1/events/ig_event")"

TOKEN="$(env_key aragorn_tk)"
if [ -z "$TOKEN" ]; then echo "FAIL: could not read aragorn_tk from .env"; FAILS=$((FAILS+1)); fi
check "ig_event valid token, missing ig_link query param -> 422" "422" \
  "$(code -X POST -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/events/ig_event")"
check "manual_event valid token, empty body -> 422" "422" \
  "$(code -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' "$BASE/api/v1/events/manual_event")"

TMPF="$(mktemp /tmp/aragorn-notanimage.XXXXXX.txt)"; echo hello > "$TMPF"
check "image_event non-image upload -> 400" "400" \
  "$(code -X POST -H "Authorization: Bearer $TOKEN" -F "event_detail_image=@$TMPF" -F "event_image=@$TMPF" "$BASE/api/v1/events/image_event")"
rm -f "$TMPF"

if [ "${1:-}" = "--e2e" ]; then
  echo "== e2e: ONE real event through Telegram + SQLite (self-cleaning) =="
  TITLE="TEST - Aragorn smoke $(date +%H:%M:%S)"
  RESP="$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"title\":\"$TITLE\",\"date\":\"1404-06-30\",\"time\":\"20:00\",\"description\":\"Aragorn run-skill e2e; auto-deleted.\",\"location\":\"35.6892, 51.3890\",\"performers\":\"Smoke Tester\",\"ticket_info\":\"not-a-real-ticket\",\"instagram_link\":\"\"}" \
    "$BASE/api/v1/events/manual_event")"
  MSG_ID="$("$PY" -c "import json,sys; d=json.loads(sys.argv[1]); print(d['tg_response']['result']['message_id'] if d.get('tg_response',{}).get('ok') else '')" "$RESP" 2>/dev/null)"
  if [ -n "$MSG_ID" ]; then
    echo "PASS: Telegram accepted event (message_id=$MSG_ID, now deleting)"
  else
    echo "FAIL: Telegram send failed: $RESP"; FAILS=$((FAILS+1))
  fi
  DB="$(env_key database_file_path)"; DB="${DB:-aragorn_db.sqlite}"
  ROWID="$(sqlite3 "$DB" "SELECT rowid FROM events WHERE title='$TITLE' ORDER BY rowid DESC LIMIT 1;")"
  if [ -n "$ROWID" ]; then
    echo "PASS: event stored in $DB (rowid=$ROWID, now deleting)"
  else
    echo "FAIL: no DB row for $TITLE"; FAILS=$((FAILS+1))
  fi
  BT="$(env_key telegram_bot_tk)"; CH="$(env_key telegram_chat)"
  if [ -n "$MSG_ID" ] && [ -n "$BT" ] && [ -n "$CH" ]; then
    OK="$("$PY" -c "import json,urllib.request,urllib.parse; q=urllib.parse.urlencode({'chat_id':'$CH','message_id':$MSG_ID}); print(json.load(urllib.request.urlopen(f'https://api.telegram.org/bot$BT/deleteMessage?{q}'))['ok'])" 2>/dev/null)"
    check "Telegram test message deleted" "True" "$OK"
  fi
  if [ -n "$ROWID" ]; then
    sqlite3 "$DB" "DELETE FROM events WHERE rowid=$ROWID AND title='$TITLE';"
    check "DB test row deleted" "1" "$(sqlite3 "$DB" "SELECT changes();")"
  fi
fi

echo "== stopping server =="
if [ "$FAILS" -eq 0 ]; then echo "ALL PASS"; else echo "$FAILS CHECK(S) FAILED"; fi
exit $([ "$FAILS" -eq 0 ] && echo 0 || echo 1)
