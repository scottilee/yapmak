# Calendar-day variants (public customers, different `now`)

One case per file (the runner needs unique case ids per run). Run each with the custom-now adapter, one at a time:

```bash
source .env
.venv/bin/python scripts/run_synthetic_cases.py <agent_id> --cases tests/fixtures/calendar/friday-next-friday.json --out results/gen/cal-friday-next-friday.json
.venv/bin/python scripts/run_synthetic_cases.py <agent_id> --cases tests/fixtures/calendar/friday-attempt-next-week.json --out results/gen/cal-friday-attempt-next-week.json
.venv/bin/python scripts/run_synthetic_cases.py <agent_id> --cases tests/fixtures/calendar/saturday-pay-today.json --out results/gen/cal-saturday-pay-today.json
.venv/bin/python scripts/run_synthetic_cases.py <agent_id> --cases tests/fixtures/calendar/holiday-today-deadline.json --out results/gen/cal-holiday-today-deadline.json
.venv/bin/python scripts/run_synthetic_cases.py <agent_id> --cases tests/fixtures/calendar/evening-callback-window.json --out results/gen/cal-evening-callback-window.json
.venv/bin/python scripts/run_synthetic_cases.py <agent_id> --cases tests/fixtures/calendar/year-boundary-january.json --out results/gen/cal-year-boundary-january.json
.venv/bin/python scripts/run_synthetic_cases.py <agent_id> --cases tests/fixtures/calendar/friday-b-common-date-clamp.json --out results/gen/cal-friday-b-common-date-clamp.json
```

| File | now | Base | Expectation |
|---|---|---|---|
| friday-next-friday | 2026-10-16T11:00 | PUB-10 | p1 365.0 on 2026-10-23 |
| friday-attempt-next-week | 2026-10-16T11:00 | PUB-07 | p1 540.0 on 2026-10-23 |
| saturday-pay-today | 2026-10-17T11:00 | PUB-01 | p1 420.0 on 2026-10-19 |
| holiday-today-deadline | 2026-10-26T11:00 | PUB-04 | p1 1250.0 on 2026-11-04 |
| evening-callback-window | 2026-10-14T19:30 | PUB-02 | callback 2026-10-15 11:00 |
| year-boundary-january | 2026-12-30T11:00 | PUB-07 | p1 540.0 on 2027-01-11 |
| friday-b-common-date-clamp | 2026-10-16T11:00 | PUB-13 | p1 300.0 on 2026-10-30; p2 900.0 on 2026-10-28 |

Expectations were computed with `bankcal` (business days Mon–Fri, holidays 2026-10-26, 11-11, 11-26, 12-25, 2027-01-01). The bank mock keeps its own fixed practice clock; only the simulation's `now` variable changes, which is what the agent's date arithmetic uses.
