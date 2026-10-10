#!/usr/bin/env bash
# When the current batch (run7) has finished, publish the PUB-10 retry fix and run the three-repetition finals.
cd "$(dirname "$0")/.." && source .env
until grep -q "^exit A-corrects" results/gen/run7.log; do sleep 30; done
echo "publish $(date -u +%FT%TZ)"
.venv/bin/python scripts/publish_check.py gen-a out/gen-a.workflow.json --no-chat 2>&1 | grep -E "published|rror"
.venv/bin/python scripts/publish_check.py gen-ab out/gen-ab.workflow.json --no-chat 2>&1 | grep -E "published|rror"
for spec in "A-reps3 a-reps3 82d0876d-b628-4bb3-98d8-4033740b7b53 --brief A --reps 3" "B-reps3 b-reps3 8912d228-94d9-4308-b85c-3054f1ff15a6 --brief B --reps 3"; do
  set -- $spec; name=$1; out=$2; shift 2
  echo "start $name $(date -u +%FT%TZ)"; .venv/bin/python -u tools/run_cases.py "$@" --out results/gen/$out.json; echo "exit $name $? $(date -u +%FT%TZ)"
done
