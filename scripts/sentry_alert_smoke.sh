#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${BACKEND_URL:-}" || -z "${ALERTS_TEST_TOKEN:-}" ]]; then
  echo "Usage: BACKEND_URL=https://... ALERTS_TEST_TOKEN=... $0"
  exit 1
fi

code="$(curl -sS -o /tmp/swl_sentry_alert_smoke.json -w "%{http_code}" \
  -X POST "${BACKEND_URL}/health/alerts/test" \
  -H "X-Alerts-Test-Token: ${ALERTS_TEST_TOKEN}")"

if [[ "$code" -lt 200 || "$code" -ge 300 ]]; then
  echo "FAIL sentry alert smoke -> HTTP ${code}"
  cat /tmp/swl_sentry_alert_smoke.json || true
  exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('/tmp/swl_sentry_alert_smoke.json').read_text())
print("OK   sentry alert smoke")
print("event_id:", payload.get("event_id", ""))
print("marker:", payload.get("marker", ""))
PY
