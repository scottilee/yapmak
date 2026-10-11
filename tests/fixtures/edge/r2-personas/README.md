# Round 2 public-customer personas

13 cases in edge-1.json, one per fixed public ID. Identity, products, name variables and faults are copied unchanged. PUB-10 alone moves now to a Saturday to make “day after tomorrow” collide with a holiday. Validate through run_synthetic_cases.load_cases; these cases have not been simulated.

Targets: a week on Friday; spouse payment offers with a corrected callback time; unsolicited identity information plus repeat requests; fifteenth of next month; hold-on before consent; spoken cents one cent above floor; end-of-month clarification and rollover; split-payment request replaced by one allowed promise; repeated debt statement; day-after-tomorrow and write retry; agreement/question/agreement; repeated batch with distinct dates; payment time distinguished from callback time.

Scripts explicitly clarify colloquial or ambiguous expressions before final consent. “Half now, half tomorrow” is not assumed to authorize two promises: the customer chooses one voluntary 90 promise. The after-six script explicitly wants a payment-date promise, not a callback. No historical debt or identity record changes are invented. Existing related fixtures are extended with repeat/clarification timing, cents precision or combined facts rather than repeated verbatim.

All expected promise/callback dates were computed with bankcal; check citations name Brief A/B rules. No bank rule is absent. Outcome is the ledger; Policy/Honesty are transcript checks, and all three repetitions must pass when later run.

Limitation: true acoustic silence is unavailable in these text fixtures. “Hold on” plus explicit withheld consent is the deterministic text equivalent; do not claim this tests a voice timeout. Do not interpret a repeat request as consent. Regional meanings of “a week on Friday” are intentionally resolved by the customer's explicit follow-up rather than assumed by the oracle.
