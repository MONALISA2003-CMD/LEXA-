#!/usr/bin/env bash
set -euo pipefail
API_URL="${1:-}"
if [[ -z "$API_URL" ]]; then
  echo "Usage: $0 https://<render-service>.onrender.com"
  exit 2
fi
API_URL="${API_URL%/}"
echo "== /health =="
curl -fsS -i "$API_URL/health" | sed -n '1,20p'
echo
echo "== /ready =="
curl -fsS -i "$API_URL/ready" | sed -n '1,30p'
echo
echo "== /dev-session =="
curl -sS -o /tmp/lexa-dev-session.json -w 'HTTP %{http_code}\n' -X POST "$API_URL/api/v1/auth/dev-session" -H 'Accept: application/json'
cat /tmp/lexa-dev-session.json
