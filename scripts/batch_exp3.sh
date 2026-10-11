#!/usr/bin/env bash
# After exp2: PUB-12 reps 2 on variants D (compact schema) and E (schema off), B slot
cd "$(dirname "$0")/.." && source .env
T=/home/agent/.claude/jobs/82832bf8/tmp/exp
B=8912d228-94d9-4308-b85c-3054f1ff15a6
healthy() {
  m=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  f=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -H "Authorization: Bearer $FREYA_API_KEY" -H "User-Agent: Mozilla/5.0 (build-the-builder)" "$FREYA_API_URL/api/v2/workspaces")
  [ "$m" = "200" ] && [ "$f" = "200" ]
}
{
until grep -q "exp2 done" results/gen/exp2.log 2>/dev/null; do sleep 60; done
for v in D E; do
  until healthy; do echo "waiting: unhealthy $(date -u +%FT%TZ)"; sleep 90; done
  echo "== variant $v $(date -u +%FT%TZ)"
  .venv/bin/python scripts/publish_check.py gen-ab $T/gen-ab-$v.workflow.json --no-chat 2>&1 | grep -E "published|rror"
  for attempt in 1 2; do
    if timeout 1500 .venv/bin/python -u tools/run_cases.py $B --cases $T/pub12.json --reps 2 --out results/gen/exp3-$v.json > results/gen/exp3-$v.txt 2> results/gen/exp3-$v.err; then break; fi
    echo "variant $v attempt $attempt failed: $(tail -1 results/gen/exp3-$v.err | cut -c1-100)"; sleep 120
  done
  echo "variant $v :: $(grep -E 'passed \(bank records' results/gen/exp3-$v.txt | tail -1 | cut -c1-60) $(date -u +%FT%TZ)"
done
echo "exp3 done $(date -u +%FT%TZ)"
} >> results/gen/exp3.log 2>&1
