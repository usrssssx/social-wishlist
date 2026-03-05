#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${BACKEND_URL:-}" || -z "${FRONTEND_URL:-}" ]]; then
  echo "Usage: BACKEND_URL=https://... FRONTEND_URL=https://... [SHARE_TOKEN=...] [CAPTCHA_TOKEN=...] $0"
  exit 1
fi

require_http_ok() {
  local url="$1"
  local code
  code="$(curl -sS -o /tmp/swl_smoke_body.txt -w "%{http_code}" "$url")"
  if [[ "$code" -lt 200 || "$code" -ge 400 ]]; then
    echo "FAIL $url -> HTTP $code"
    cat /tmp/swl_smoke_body.txt || true
    exit 1
  fi
  echo "OK   $url -> HTTP $code"
}

json_get() {
  local key="$1"
  local payload
  payload="$(cat)"
  JSON_INPUT="$payload" \
  python3 - "$key" <<'PY'
import json
import os
import sys

key = sys.argv[1]
raw = os.environ.get("JSON_INPUT", "").strip()
if not raw:
    sys.exit(1)
data = json.loads(raw)
value = data.get(key)
if value is None:
    sys.exit(1)
print(value)
PY
}

echo "[1/4] Frontend availability"
require_http_ok "${FRONTEND_URL}"

echo "[2/4] Backend health"
health_json="$(curl -sS "${BACKEND_URL}/health")"
status="$(printf '%s' "$health_json" | json_get status || true)"
db_ok="$(printf '%s' "$health_json" | json_get db || true)"
if [[ "$status" != "ok" || "$db_ok" != "True" ]]; then
  echo "FAIL health check: $health_json"
  exit 1
fi
echo "OK   /health status=${status} db=${db_ok}"

echo "[3/4] Public API base check"
if [[ -n "${SHARE_TOKEN:-}" ]]; then
  code="$(curl -sS -o /tmp/swl_public.json -w "%{http_code}" "${BACKEND_URL}/api/public/w/${SHARE_TOKEN}")"
  if [[ "$code" -ge 400 ]]; then
    echo "FAIL public wishlist: HTTP $code"
    cat /tmp/swl_public.json || true
    exit 1
  fi
  echo "OK   public wishlist HTTP ${code}"
else
  echo "SKIP public check (SHARE_TOKEN is not set)"
fi

echo "[4/4] Guest session smoke"
if [[ -n "${SHARE_TOKEN:-}" ]]; then
  payload="$(python3 - <<'PY'
import json
import os

print(json.dumps({
    "display_name": "Smoke Guest",
    "captcha_token": os.getenv("CAPTCHA_TOKEN"),
}))
PY
)"
  code="$(curl -sS -o /tmp/swl_guest.json -w "%{http_code}" \
    -X POST "${BACKEND_URL}/api/public/w/${SHARE_TOKEN}/sessions" \
    -H "Content-Type: application/json" \
    -d "$payload")"
  if [[ "$code" -ge 400 ]]; then
    echo "FAIL guest session: HTTP $code"
    cat /tmp/swl_guest.json || true
    exit 1
  fi
  echo "OK   guest session HTTP ${code}"
else
  echo "SKIP guest session (SHARE_TOKEN is not set)"
fi

echo "Smoke checks completed successfully."
