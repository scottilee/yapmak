# v24 branch-focused live inputs

These 13 cases are future live inputs only. No simulations were run while authoring them. All records are copied from the public set; identities, products and faults remain unchanged. Each file contains unique customer IDs. Run files separately and use the matching A/B phone agent; do not concatenate duplicate IDs.

| File | Cases | Targets |
|---|---:|---|
| v24-branches-a1.json | 5 | Robot question with acceptance; scam question with final confirmation; explicit goodbye mid-negotiation and at read-back; Monday the 26th |
| v24-branches-a2.json | 4 | Offered Tuesday acceptance versus explicit Tuesday correction; chatter carrying amount/date; robot question at final confirmation |
| v24-branches-b1.json | 3 | Common dates across differing product deadlines, including holiday/weekend rollover before batch confirmation |
| v24-branches-b2.json | 1 | Call-wide termination abandons a pending card proposal and refuses all unfinished products |

Every script specifies what to repeat if clarified and which read-back can be confirmed. The final-confirmation asides contain an unconditional yes; the question does not revoke consent. The goodbye scripts explicitly reject consent and/or repeat refusal to talk, avoiding the ambiguity of a casual “thanks.” Tests assert the bank rules, not current implementation behavior.

Dates were computed with bankcal.resolve_date_expr, next_business_day and deadline. Practice clock: next day 15 October; explicit Tuesday 20 October; Monday 26 October is a holiday and rolls to Tuesday 27 October; 31 October rolls to 2 November. Late/early deadlines are 23 October/2 November. PUB-13 in b1 alone uses now=2026-10-23T11:00: deadlines are 4 November/12 November, so the shared 5 November proposal remains 5 November for the card and caps to 4 November for the loan. All expected promise dates were checked against business days and product-specific deadlines; all amounts against floor/full.

These intentionally revisit requested v24 branches rather than claiming wholly novel policy families. In particular, the negative Tuesday-correction control prevents an over-broad “same weekday means same offer” fix. The B1 variants place the product requiring rollover at different positions, so early loop returns and lost batch state are observable. The grader should require an honest robot/scam answer somewhere before closing; it should not impose an invented ordering between that answer and an already authorized write.

Offline loader validation (does not simulate):

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -c "import sys; sys.path.insert(0,'scripts'); from run_synthetic_cases import load_cases; [load_cases('tests/fixtures/edge/v24-branches-'+n+'.json') for n in ('a1','a2','b1','b2')]"
```

No live command is executed here. Use scripts/run_synthetic_cases.py with --cases and your intended agent ID during the final batch window. Customer/model wording remains stochastic; these are gold expectations, not claimed passing transcripts.
