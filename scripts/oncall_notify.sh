#!/usr/bin/env bash
set -euo pipefail

MESSAGE="${1:-}"
if [[ -z "$MESSAGE" ]]; then
  echo "Usage: $0 \"message\""
  exit 1
fi

sent=false

if [[ -n "${ONCALL_SLACK_WEBHOOK_URL:-}" ]]; then
  payload="$(jq -nc --arg text "$MESSAGE" '{text:$text}')"
  curl -sS -X POST -H "Content-Type: application/json" \
    -d "$payload" "${ONCALL_SLACK_WEBHOOK_URL}" >/dev/null
  sent=true
fi

if [[ -n "${ONCALL_TELEGRAM_BOT_TOKEN:-}" && -n "${ONCALL_TELEGRAM_CHAT_ID:-}" ]]; then
  curl -sS -X POST "https://api.telegram.org/bot${ONCALL_TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${ONCALL_TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${MESSAGE}" >/dev/null
  sent=true
fi

if [[ -n "${ONCALL_WEBHOOK_URL:-}" ]]; then
  payload="$(jq -nc --arg text "$MESSAGE" '{text:$text, source:"social-wishlist"}')"
  curl -sS -X POST -H "Content-Type: application/json" \
    -d "$payload" "${ONCALL_WEBHOOK_URL}" >/dev/null
  sent=true
fi

if [[ "$sent" != "true" ]]; then
  echo "No on-call channel configured"
  exit 1
fi

echo "On-call notification sent"
