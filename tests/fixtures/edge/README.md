# Additional live edges: codex-1 and codex-2

These **15 new cases** supplement the existing edge-a*/edge-b* fixtures; they do not replace them. `codex-1.json` contains each public customer once (13 cases). `codex-2.json` contains PUB-11 and PUB-13 once each (2 variants). Run files separately; do not concatenate duplicate customer IDs. Filter A/B when selecting the corresponding generated agent.

The script/ledger changes preserve each public customer's ID, brief, name, identity, products and faults exactly. PUB-10 still fails its first promise write. Only that case changes `now` (to 2026-10-23T11:00). Each case includes a rule-number rationale and judge checks; all files passed `run_synthetic_cases.load_cases` offline.

| File / customer | New interaction targeted |
|---|---|
| 1 / PUB-01 | Both identity facts volunteered in the opening; no skipped verification |
| 1 / PUB-02 | Persistent third-party payment offer plus equal-to-now rejection and 19:00 boundary |
| 1 / PUB-03 | Two wrong birth dates, correct birth date, then wrong digits: global counter |
| 1 / PUB-04 | Valid amount in words plus late date in the same utterance |
| 1 / PUB-05 | Job loss and lower-instalment request together: hardship wins |
| 1 / PUB-06 | Explicitly revoked hedge; amount and date both changed at read-back |
| 1 / PUB-07 | Acceptance plus robot question, then explicitly withheld consent for another question |
| 1 / PUB-08 | Historical payoff/closure versus payment of current arrears |
| 1 / PUB-09 | Human request withdrawn after the assistant's help offer |
| 1 / PUB-10 | Weekend + holiday rollover combined with the real first-write fault |
| 1 / PUB-11 | Promise/dispute/hardship facts followed by support transfer before confirmation |
| 1 / PUB-12 | Out-of-order product reference: p3 promise, p1 paid, p2 disputed |
| 1 / PUB-13 | Common holiday rolls early product forward but caps late product at its earlier deadline |
| 2 / PUB-11 | Qualified yes disputes one batch item; remaining items need fresh confirmation |
| 2 / PUB-13 | Paid + disputed, no promises: first non-paid note decides outcome |

Dates were computed with `bankcal.parse_now`, `resolve_date_expr`, `last_business_day_of_week`, `next_business_day` and `deadline`; no calendar arithmetic was done by hand. For the practice clock, computed tomorrow is 2026-10-15, week-end offer 2026-10-16, following Monday 2026-10-19, late deadline 2026-10-23 and early deadline 2026-11-02. The common holiday 2026-10-26 rolls to 2026-10-27. For PUB-10's alternate clock, tomorrow 2026-10-24 rolls to 2026-10-27, before its computed deadline 2026-11-04. All expected payment dates were checked against product-specific floors, balances, business days and deadlines; the callback boundaries were checked using `bankcal.callback_ok`.

No simulation, extraction, build or Freya API call was made. The public website was read only for scoring: ledger outcome plus judged policy/honesty, and all three repetitions must pass. Customer wording and judge behavior are still stochastic; these files are intended future inputs, not claimed passing results.

Ambiguity choices: a bare “I suppose so” is not assigned a controversial gold label; the case explicitly revokes it. The mixed-hardship case accepts a support transfer, avoiding the practice brief's less explicit treatment of product-scoped hardship refusal. Unsolicited identity data may be repeated when properly asked; the oracle requires successful verification, not a particular conversational shortcut. No invented product is added to the fixed mock. Named out-of-order products all exist in that customer's record.

Validation only (does not simulate):
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import run_synthetic_cases as r; r.load_cases('tests/fixtures/edge/codex-1.json'); r.load_cases('tests/fixtures/edge/codex-2.json')"
```
