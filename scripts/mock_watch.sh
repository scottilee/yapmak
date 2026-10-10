#!/usr/bin/env bash
# Log the bank mock's health every 3 minutes (status transitions only) so outages can be matched to run results.
cd "$(dirname "$0")/.." && source .env
last=""
for i in $(seq 1 400); do
  code=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  state="healthy"; [ "$code" = "200" ] || state="DOWN ($code)"
  if [ "$state" != "$last" ]; then echo "$(date -u +%FT%TZ) mock $state"; last="$state"; fi
  sleep 180
done
