#!/usr/bin/env bash
# Variant G (fixed-text hand-over + FULL compound schema): PUB-12 reps 3, then the unlike-round B edge set; B slot
cd "$(dirname "$0")/.." && source .env
unset FREYA_BUILD_DEADLINE BUILD_DEADLINE RUNCONTROL_DEADLINE 2>/dev/null
T=/home/agent/.claude/jobs/82832bf8/tmp/exp
B=8912d228-94d9-4308-b85c-3054f1ff15a6
healthy() {
  m=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  f=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -H "Authorization: Bearer $FREYA_API_KEY" -H "User-Agent: Mozilla/5.0 (build-the-builder)" "$FREYA_API_URL/api/v2/workspaces")
  [ "$m" = "200" ] && [ "$f" = "200" ]
}
run() { name=$1; out=$2; shift 2
  for attempt in 1 2 3; do
    until healthy; do echo "waiting: unhealthy $(date -u +%FT%TZ)"; sleep 90; done
    if timeout 2400 .venv/bin/python -u "$@" --out results/gen/$out.json > results/gen/$out.txt 2> results/gen/$out.err; then
      echo "exit $name 0 :: $(grep -E 'passed \(bank records' results/gen/$out.txt | tail -1 | cut -c1-70) $(date -u +%FT%TZ)"; return; fi
    echo "exit $name FAILED attempt $attempt: $(tail -1 results/gen/$out.err | cut -c1-120) $(date -u +%FT%TZ)"; sleep 120
  done; }
{
until healthy; do sleep 60; done
echo "== variant G $(date -u +%FT%TZ)"
.venv/bin/python scripts/publish_check.py gen-ab $T/gen-ab-G.workflow.json --no-chat 2>&1 | grep -E "published|rror"
run G-pub12 exp5-G-pub12 tools/run_cases.py $B --cases $T/pub12.json --reps 3
run G-edge1b exp5-G-edge1b scripts/run_synthetic_cases.py $B --cases /home/agent/.claude/jobs/82832bf8/tmp/edge1-b.json
echo "exp5 done $(date -u +%FT%TZ)"
} >> results/gen/exp5.log 2>&1
