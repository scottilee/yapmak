#!/usr/bin/env bash
# v25g commit gate after the outage: re-publish, A x3, B x3; then variant G (hand-over + full schema) PUB-12 x3 + unlike-round B edge set
cd "$(dirname "$0")/.." && source .env
T=/home/agent/.claude/jobs/82832bf8/tmp
A=82d0876d-b628-4bb3-98d8-4033740b7b53; B=8912d228-94d9-4308-b85c-3054f1ff15a6
healthy() {
  m=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  f=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -H "Authorization: Bearer $FREYA_API_KEY" -H "User-Agent: Mozilla/5.0 (build-the-builder)" "$FREYA_API_URL/api/v2/workspaces")
  [ "$m" = "200" ] && [ "$f" = "200" ]
}
pub() { slot=$1; file=$2; for i in 1 2 3 4; do until healthy; do sleep 60; done; if .venv/bin/python scripts/publish_check.py $slot $file --no-chat 2>&1 | grep -E "published"; then return 0; fi; echo "publish $slot attempt $i failed"; sleep 60; done; return 1; }
run() { name=$1; out=$2; shift 2
  for attempt in 1 2 3; do
    until healthy; do echo "waiting: unhealthy $(date -u +%FT%TZ)"; sleep 90; done
    if timeout 2400 .venv/bin/python -u "$@" --out results/gen/$out.json > results/gen/$out.txt 2> results/gen/$out.err; then
      echo "exit $name 0 :: $(grep -E 'passed \(bank records' results/gen/$out.txt | tail -1 | cut -c1-70) $(date -u +%FT%TZ)"; return; fi
    echo "exit $name FAILED attempt $attempt: $(tail -1 results/gen/$out.err | cut -c1-120) $(date -u +%FT%TZ)"; sleep 120
  done; }
{
echo "== v25g gate $(date -u +%FT%TZ)"
pub gen-a $T/v25g/gen-a.workflow.json; pub gen-ab $T/v25g/gen-ab.workflow.json
run A-reps3 r25g2-a-reps3 tools/run_cases.py $A --brief A --reps 3
run B-reps3 r25g2-b-reps3 tools/run_cases.py $B --brief B --reps 3
echo "== variant G $(date -u +%FT%TZ)"
pub gen-ab $T/exp/gen-ab-G.workflow.json
run G-pub12 exp6-G-pub12 tools/run_cases.py $B --cases $T/exp/pub12.json --reps 3
run G-edge1b exp6-G-edge1b scripts/run_synthetic_cases.py $B --cases $T/edge1-b.json
echo "batch done $(date -u +%FT%TZ)"
} >> results/gen/run25g2.log 2>&1
