#!/usr/bin/env bash
# After run25g3: restore v25g on gen-ab and run brief B x3 as the final B gate
cd "$(dirname "$0")/.." && source .env
A=82d0876d-b628-4bb3-98d8-4033740b7b53; B=8912d228-94d9-4308-b85c-3054f1ff15a6
healthy() {
  m=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  f=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -H "Authorization: Bearer $FREYA_API_KEY" -H "User-Agent: Mozilla/5.0 (build-the-builder)" "$FREYA_API_URL/api/v2/workspaces")
  [ "$m" = "200" ] && [ "$f" = "200" ]
}
stale_sims() { .venv/bin/python - <<'PY'
import sys, json; sys.path.insert(0, "."); import freya
try:
    d = freya.api("GET", "/api/v2/simulations", status="running"); sims = (d.get("result") or d).get("simulations") or []
    for s in sims:
        freya.api("DELETE", f"/api/v2/simulations/{s['id']}"); print("deleted stale simulation", s["id"][:8])
except Exception as e: print("stale check:", repr(e)[:80])
PY
}
{
until grep -q "batch done" results/gen/run25g3.log 2>/dev/null; do sleep 60; done
for i in 1 2 3 4; do until healthy; do sleep 60; done; if .venv/bin/python scripts/publish_check.py gen-ab /home/agent/.claude/jobs/82832bf8/tmp/v25g/gen-ab.workflow.json --no-chat 2>&1 | grep -E 'published'; then break; fi; echo "publish gen-ab attempt $i failed"; sleep 60; done
for attempt in 1 2 3; do
  until healthy; do echo "waiting: unhealthy $(date -u +%FT%TZ)"; sleep 90; done
  stale_sims
  if timeout 2400 .venv/bin/python -u tools/run_cases.py $B --brief B --reps 3 --out results/gen/r25g4-b-reps3.json > results/gen/r25g4-b-reps3.txt 2> results/gen/r25g4-b-reps3.err; then
    echo "exit B-reps3 0 :: $(grep -E 'passed \(bank records' results/gen/r25g4-b-reps3.txt | tail -1 | cut -c1-70) $(date -u +%FT%TZ)"; break; fi
  echo "exit B-reps3 FAILED attempt $attempt: $(tail -1 results/gen/r25g4-b-reps3.err | cut -c1-120) $(date -u +%FT%TZ)"; sleep 120
done
echo "batch done $(date -u +%FT%TZ)"
} >> results/gen/run25g4.log 2>&1
