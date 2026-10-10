# Current-schema priority intent sweep

Run `20261010T144657Z-priority`: **250/258 selected scenarios completed** from the 1,368-scenario corpus. **211/219 clear-oracle matches**; 9 total disagreements, including 1 mixed/underspecified cases. 8 infrastructure-error attempts. These are single observations, not consistency estimates.

Fresh schema snapshot; results from the old 39-case run are not pooled. Four concurrent isolated calls per stage on `runtime-check`; publication is sequential between stages. Only chat routes, with inert destinations and no bank tools or simulations. Negotiation/read-back context is 420 on Friday 16 October 2026, `now=2026-10-14T11:00`.

Compiler SHA-256: `49c1914a4e130aedb9c5ff03b2dda9d64ef963798d53eb143c035e2aec464812`. [Snapshot](20261010T144657Z-priority/compile.snapshot.txt), [schemas](20261010T144657Z-priority/schemas.json), [raw results](20261010T144657Z-priority/results.json), [selected cases](20261010T144657Z-priority/selected-cases.json), [oracle updates](20261010T144657Z-priority/oracle-updates.json). Compiler source was not edited.

Expected opening labels were updated **before any opening cases ran**, because the current holder enum introduces `question` for questions without confirmation. The old corpus calls these `unclear`; raw results preserve that old label, while this report applies the predeclared overrides. Questions prefixed by the asks-back style receive `question` too. No observed result was used to choose these overrides.

Five styles are transformations of six base phrasings per selected intent. Bulk `corrects` is a reformulation cue, while boundary controls include actual changed amount/date/intention. Inert test nodes retain fragments; this checks extraction, not production routing, consent invalidation, or bank writes. In pieces cases the last assistant response may change conversational context; inspect per-turn evidence before treating a disagreement as a description defect. Mixed hearing-question plus answer probes are shown separately.

## Coverage

| Stage | Expected intent | Completed / selected | Matches | In words | Pieces | Corrects | Talkative | Asks back | Boundary |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| negotiate | accepts | 31/32 | 31 | 6/6 | 5/5 | 6/6 | 6/6 | 6/6 | 2/2 |
| negotiate | other | 1/1 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/1 |
| negotiate | proposes | 30/31 | 30 | 6/6 | 5/5 | 6/6 | 6/6 | 6/6 | 1/1 |
| negotiate | question | 32/32 | 32 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 2/2 |
| negotiate | too_much | 33/33 | 32 | 6/6 | 5/6 | 6/6 | 6/6 | 6/6 | 3/3 |
| opening | question | 22/23 | 16 | 3/4 | 2/3 | 4/4 | 3/4 | 3/6 | 1/1 |
| opening | unclear | 8/9 | 8 | 2/2 | 2/2 | 2/2 | 1/1 | 0/0 | 1/1 |
| readback | changes | 31/31 | 31 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 1/1 |
| readback | confirms | 28/30 | 28 | 6/6 | 4/4 | 6/6 | 6/6 | 6/6 | 0/0 |
| readback | question | 29/31 | 29 | 5/5 | 5/5 | 6/6 | 6/6 | 6/6 | 1/1 |
| third_party | gives_time | 5/5 | 4 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 4/5 |

## Exact disagreements

| Case / evidence | Utterance(s) | Expected | Actual | Last-turn extraction | Assessment |
|---|---|---|---|---|---|
| [boundary-09](20261010T144657Z-priority/calls/boundary-09.turns.json) | You tell me. | other | question | question @ 1.0 | mixed/underspecified |
| [negotiate-too_much-pieces-6](20261010T144657Z-priority/calls/negotiate-too_much-pieces-6.turns.json) | I need a lower amount, but ... → ... you tell me what it is. | too_much | question | question @ 0.8354827688446351 | clear-oracle disagreement |
| [opening-unclear-in_words-5](20261010T144657Z-priority/calls/opening-unclear-in_words-5.turns.json) | Can you hear me? | question | unclear | unclear @ 1.0 | clear-oracle disagreement |
| [opening-unclear-pieces-5](20261010T144657Z-priority/calls/opening-unclear-pieces-5.turns.json) | Can you ... → ... hear me? | question | unclear | unclear @ 1.0 | clear-oracle disagreement |
| [opening-unclear-asks_back-2](20261010T144657Z-priority/calls/opening-unclear-asks_back-2.turns.json) | Can you hear me clearly? Go ahead. | question | unclear | unclear @ 1.0 | clear-oracle disagreement |
| [opening-unclear-talkative-5](20261010T144657Z-priority/calls/opening-unclear-talkative-5.turns.json) | I was just getting settled and there is a bit of noise here. Can you hear me? That is what I wanted to say. | question | unclear | unclear @ 1.0 | clear-oracle disagreement |
| [opening-unclear-asks_back-1](20261010T144657Z-priority/calls/opening-unclear-asks_back-1.turns.json) | Can you hear me clearly? Hello. | question | unclear | unclear @ 1.0 | clear-oracle disagreement |
| [opening-unclear-asks_back-5](20261010T144657Z-priority/calls/opening-unclear-asks_back-5.turns.json) | Can you hear me clearly? Can you hear me? | question | unclear | unclear @ 1.0 | clear-oracle disagreement |
| [boundary-17](20261010T144657Z-priority/calls/boundary-17.turns.json) | Morning. | gives_time | other | other @ 1.0 | clear-oracle disagreement |

## Boundary controls

| Case | Utterance(s) | Expected → actual | Callback clock check |
|---|---|---|---|
| boundary-01 | You tell me. → What is the smallest amount I can pay? | too_much → too_much | — |
| boundary-02 | You tell me what the deadline means. | question → question | — |
| boundary-03 | Can you offer a smaller payment? | too_much → too_much | — |
| boundary-04 | Yes, I can pay on Friday the sixteenth. | accepts → accepts | — |
| boundary-05 | Friday the sixteenth, yes, that works. | accepts → accepts | — |
| boundary-06 | Yes, actually no, I need the twentieth instead. | proposes → proposes | — |
| boundary-07 | I agree, sorry, no, that is too much; suggest less. | too_much → too_much | — |
| boundary-08 | How much did you just say? | question → question | — |
| boundary-09 | You tell me. | other → question | — |
| boundary-10 | Who is calling? | question → question | — |
| boundary-11 | Go on, I am listening. | unclear → unclear | — |
| boundary-12 | Yes, correct, actually change it to three hundred and fifty. | changes → changes | — |
| boundary-13 | Do you mean this Friday or next Friday? | question → question | — |
| boundary-14 | Tomorrow morning. → Around eleven. | gives_time → gives_time | '11:00'; pass=True |
| boundary-15 | Tomorrow. → In the morning. → Around eleven. | gives_time → gives_time | '11:00'; pass=True |
| boundary-16 | Tomorrow around... → ...eleven in the morning. | gives_time → gives_time | '11:00'; pass=True |
| boundary-17 | Morning. | gives_time → other | ''; pass=True |
| boundary-18 | Tomorrow at three, sorry, around eleven in the morning. | gives_time → gives_time | '11:00'; pass=True |

## Reproduce / continue

Continue the frozen snapshot serially (remaining full-corpus cases; original corpus labels require the documented opening adjustment):

```bash
source .env
.venv/bin/python -u scripts/intent_chat_checks.py --resume results/extraction/20261010T144657Z-priority
```

To run a fresh priority sweep against the then-current compiler: `.venv/bin/python -u scripts/intent_priority_sweep.py`.
