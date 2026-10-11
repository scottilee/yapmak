#!/usr/bin/env bash
# Experiment: which v25 change makes the dialogue model ignore the car-loan hand-over on PUB-12 (B slot only, PUB-12 only, reps 2)
cd "$(dirname "$0")/.." && source .env
T=/home/agent/.claude/jobs/82832bf8/tmp/exp
B=8912d228-94d9-4308-b85c-3054f1ff15a6
{
for v in B C A; do
  echo "== variant $v $(date -u +%FT%TZ)"
  .venv/bin/python scripts/publish_check.py gen-ab $T/gen-ab-$v.workflow.json --no-chat 2>&1 | grep -E "published|rror"
  timeout 900 .venv/bin/python -u tools/run_cases.py $B --cases $T/pub12.json --reps 2 --out results/gen/exp1-$v.json > results/gen/exp1-$v.txt 2> results/gen/exp1-$v.err
  echo "variant $v :: $(grep -E 'passed \(bank records' results/gen/exp1-$v.txt | tail -1 | cut -c1-60) $(date -u +%FT%TZ)"
done
echo "exp1 done"
} >> results/gen/exp1.log 2>&1
