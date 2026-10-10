#!/usr/bin/env bash
# After the v19 batch: publish gen-ab from the tree, then confirm v20/v19 with A --reps 3 and B --reps 3 (health-gated, retries).
cd "$(dirname "$0")/.." && source .env
until grep -q "^batch done" results/gen/run19-v19.log 2>/dev/null; do sleep 30; done
healthy() {
  m=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  f=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -H "Authorization: Bearer $FREYA_API_KEY" -H "User-Agent: Mozilla/5.0 (build-the-builder)" "$FREYA_API_URL/api/v2/workspaces")
  [ "$m" = "200" ] && [ "$f" = "200" ]
}
echo "publish gen-ab $(date -u +%FT%TZ)"; .venv/bin/python scripts/publish_check.py gen-ab out/gen-ab.workflow.json --no-chat 2>&1 | grep -E "published|rror"
A=82d0876d-b628-4bb3-98d8-4033740b7b53; B=8912d228-94d9-4308-b85c-3054f1ff15a6
for spec in "A-reps3 a-reps3-v20 $A --brief A --reps 3" "B-reps3 b-reps3-v19 $B --brief B --reps 3" "A-asks_back a-asksback-v20 $A --brief A --style asks_back"; do
  set -- $spec; name=$1; out=$2; shift 2
  for attempt in 1 2 3; do
    until healthy; do echo "waiting: mock/platform unhealthy $(date -u +%FT%TZ)"; sleep 120; done
    echo "start $name attempt $attempt $(date -u +%FT%TZ)"
    if .venv/bin/python -u tools/run_cases.py "$@" --out results/gen/$out.json 2> results/gen/$out.err; then echo "exit $name 0 $(date -u +%FT%TZ)"; break; fi
    echo "exit $name FAILED attempt $attempt: $(tail -1 results/gen/$out.err | cut -c1-120) $(date -u +%FT%TZ)"; sleep 120
  done
done
echo "batch done $(date -u +%FT%TZ)"
