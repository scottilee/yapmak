#!/usr/bin/env bash
# Wait for the platform to answer a chat turn again, then publish the current builds and run a sim batch.
cd "$(dirname "$0")/.." && source .env
for i in $(seq 1 60); do
  if .venv/bin/python - <<'PY' 2>/dev/null; then echo "platform ok $(date -u +%FT%TZ)"; break; fi
import freya, sys
r = freya.api('POST','/api/v2/chat/message', {'workflowId':'3a313c88-e790-43c4-ad2e-504199b115f1','message':'Hello?','customerVariables':{'customer_id':'c_smoke','first_name':'Test','last_name':'Customer','title':'Ms','now':'2026-10-14T11:00'}})
freya.api('POST','/api/v2/chat/end', {'callId': r['callId']})
sys.exit(0 if r.get('response') else 1)
PY
  echo "platform down, retry $i $(date -u +%FT%TZ)"; sleep 120
done
echo "publish $(date -u +%FT%TZ)"
.venv/bin/python scripts/publish_check.py gen-a out/gen-a.workflow.json --no-chat 2>&1 | grep -E "published|rror"
.venv/bin/python scripts/publish_check.py gen-ab out/gen-ab.workflow.json --no-chat 2>&1 | grep -E "published|rror"
for spec in "A a-run7 82d0876d-b628-4bb3-98d8-4033740b7b53 --brief A" "B b-run4 8912d228-94d9-4308-b85c-3054f1ff15a6 --brief B" "A-asks_back a-asksback3 82d0876d-b628-4bb3-98d8-4033740b7b53 --brief A --style asks_back" "B-pieces b-pieces3 8912d228-94d9-4308-b85c-3054f1ff15a6 --brief B --style pieces" "A-corrects a-corrects3 82d0876d-b628-4bb3-98d8-4033740b7b53 --brief A --style corrects"; do
  set -- $spec; name=$1; out=$2; shift 2
  echo "start $name $(date -u +%FT%TZ)"; .venv/bin/python -u tools/run_cases.py "$@" --out results/gen/$out.json; echo "exit $name $? $(date -u +%FT%TZ)"
done
