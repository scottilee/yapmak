#!/usr/bin/env bash
# v19/v18 confirmation: hardship fix. Health-gated, 3 attempts per run.
cd "$(dirname "$0")/.." && source .env
healthy() {
  m=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  f=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -H "Authorization: Bearer $FREYA_API_KEY" -H "User-Agent: Mozilla/5.0 (build-the-builder)" "$FREYA_API_URL/api/v2/workspaces")
  [ "$m" = "200" ] && [ "$f" = "200" ]
}
A=82d0876d-b628-4bb3-98d8-4033740b7b53; B=8912d228-94d9-4308-b85c-3054f1ff15a6
for spec in "A-reps3 a-reps3-v19 $A --brief A --reps 3" "A-asks_back a-asksback-v19 $A --brief A --style asks_back" "A-corrects a-corrects-v19 $A --brief A --style corrects" "A-talkative a-talkative-v19 $A --brief A --style talkative" "B b-v18 $B --brief B"; do
  set -- $spec; name=$1; out=$2; shift 2
  for attempt in 1 2 3; do
    until healthy; do echo "waiting: mock/platform unhealthy $(date -u +%FT%TZ)"; sleep 120; done
    echo "start $name attempt $attempt $(date -u +%FT%TZ)"
    if .venv/bin/python -u tools/run_cases.py "$@" --out results/gen/$out.json 2> results/gen/$out.err; then echo "exit $name 0 $(date -u +%FT%TZ)"; break; fi
    echo "exit $name FAILED attempt $attempt: $(tail -1 results/gen/$out.err | cut -c1-120) $(date -u +%FT%TZ)"; sleep 120
  done
done
echo "batch done $(date -u +%FT%TZ)"
