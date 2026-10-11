#!/usr/bin/env bash
# The other agent's 15 live edge cases on the published final v23 slots.
cd "$(dirname "$0")/.." && source .env
LOG=results/gen/run-codex.log
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
run codex-1-A rcodex-1-a scripts/run_synthetic_cases.py $A --cases tests/fixtures/edge/codex-1.json --brief A
run codex-1-B rcodex-1-b scripts/run_synthetic_cases.py $B --cases tests/fixtures/edge/codex-1.json --brief B
run codex-2-B rcodex-2-b scripts/run_synthetic_cases.py $B --cases tests/fixtures/edge/codex-2.json
echo "batch done $(date -u +%FT%TZ)"
} >> $LOG 2>&1
