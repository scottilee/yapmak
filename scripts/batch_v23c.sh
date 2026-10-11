#!/usr/bin/env bash
# v23 with the chatter/goodbye rule: talkative on A and B, B reps 3, A reps 3, the two edge sets.
cd "$(dirname "$0")/.." && source .env
LOG=results/gen/run23c.log
healthy() {
  m=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  f=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -H "Authorization: Bearer $FREYA_API_KEY" -H "User-Agent: Mozilla/5.0 (build-the-builder)" "$FREYA_API_URL/api/v2/workspaces")
  [ "$m" = "200" ] && [ "$f" = "200" ]
}
run() { name=$1; out=$2; shift 2
  for attempt in 1 2 3; do
    until healthy; do echo "waiting: mock/platform unhealthy $(date -u +%FT%TZ)"; sleep 120; done
    echo "start $name attempt $attempt $(date -u +%FT%TZ)"
    if .venv/bin/python -u "$@" --out results/gen/$out.json 2> results/gen/$out.err > results/gen/$out.txt; then
      echo "exit $name 0 :: $(grep -E 'passed \(bank records' results/gen/$out.txt | tail -1 | cut -c1-80) $(date -u +%FT%TZ)"; break; fi
    echo "exit $name FAILED attempt $attempt: $(tail -1 results/gen/$out.err | cut -c1-120) $(date -u +%FT%TZ)"; sleep 120
  done; }
{
A=82d0876d-b628-4bb3-98d8-4033740b7b53; B=8912d228-94d9-4308-b85c-3054f1ff15a6
run B-talkative r23c-b-talkative tools/run_cases.py $B --brief B --style talkative
run A-talkative r23c-a-talkative tools/run_cases.py $A --brief A --style talkative
run B-reps3 r23c-b-reps3 tools/run_cases.py $B --brief B --reps 3
run A-reps3 r23c-a-reps3 tools/run_cases.py $A --brief A --reps 3
run edge-a3 r23c-edge-a3 scripts/run_synthetic_cases.py $A --cases tests/fixtures/edge/edge-a3.json
run edge-b2 r23c-edge-b2 scripts/run_synthetic_cases.py $B --cases tests/fixtures/edge/edge-b2.json
run edge-a1 r23c-edge-a1 scripts/run_synthetic_cases.py $A --cases tests/fixtures/edge/edge-a1.json
echo "batch done $(date -u +%FT%TZ)"
} >> $LOG 2>&1
