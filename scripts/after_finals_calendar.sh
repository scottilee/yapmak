#!/usr/bin/env bash
# After the --reps 3 finals, run the seven calendar-day variants one at a time (custom-now adapter).
cd "$(dirname "$0")/.." && source .env
until grep -q "^exit B-reps3" results/gen/run8.log 2>/dev/null; do sleep 30; done
A=82d0876d-b628-4bb3-98d8-4033740b7b53; B=8912d228-94d9-4308-b85c-3054f1ff15a6
for f in friday-next-friday friday-attempt-next-week saturday-pay-today holiday-today-deadline evening-callback-window year-boundary-january friday-b-common-date-clamp; do
  agent=$A; [ "$f" = "friday-b-common-date-clamp" ] && agent=$B
  echo "start $f $(date -u +%FT%TZ)"; .venv/bin/python -u scripts/run_synthetic_cases.py $agent --cases tests/fixtures/calendar/$f.json --out results/gen/cal-$f.json; echo "exit $f $? $(date -u +%FT%TZ)"
done
