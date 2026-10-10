#!/usr/bin/env bash
# Wait for the bank mock (Cloudflare worker) to answer session creation again, then run the v14 verification batch.
cd "$(dirname "$0")/.." && source .env
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "content-type: application/json" -H "x-team-key: $FREYA_BANK_TEAM_KEY" -H "user-agent: freya-bank-scorer/0.1" -d '{"case":"PUB-01"}' https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions)
  if [ "$code" = "200" ]; then echo "mock ok $(date -u +%FT%TZ)"; break; fi
  echo "mock down ($code), retry $i $(date -u +%FT%TZ)"; sleep 120
done
A=82d0876d-b628-4bb3-98d8-4033740b7b53; B=8912d228-94d9-4308-b85c-3054f1ff15a6
for spec in "A a-v14 $A --brief A" "B b-v13 $B --brief B" "A-asks_back a-asksback-v14 $A --brief A --style asks_back" "A-talkative a-talkative-v14 $A --brief A --style talkative" "B-talkative b-talkative-v13 $B --brief B --style talkative" "A-corrects a-corrects-v14 $A --brief A --style corrects" "A-pieces a-pieces-v14 $A --brief A --style pieces" "B-corrects b-corrects-v13 $B --brief B --style corrects"; do
  set -- $spec; name=$1; out=$2; shift 2
  echo "start $name $(date -u +%FT%TZ)"; .venv/bin/python -u tools/run_cases.py "$@" --out results/gen/$out.json; echo "exit $name $? $(date -u +%FT%TZ)"
done
