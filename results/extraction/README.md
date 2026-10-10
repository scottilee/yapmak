# Current-schema priority intent sweep

Run `20261010T144657Z-priority`: **258/258 selected scenarios completed** from the 1,368-scenario corpus. **219/227 clear-oracle matches**; 9 total disagreements, including 1 mixed/underspecified cases. 8 infrastructure-error attempts. These are single observations, not consistency estimates.

Fresh schema snapshot; results from the old 39-case run are not pooled. Four concurrent isolated calls per stage on `runtime-check`; publication is sequential between stages. Only chat routes, with inert destinations and no bank tools or simulations. Negotiation/read-back context is 420 on Friday 16 October 2026, `now=2026-10-14T11:00`.

Compiler SHA-256: `49c1914a4e130aedb9c5ff03b2dda9d64ef963798d53eb143c035e2aec464812`. [Snapshot](20261010T144657Z-priority/compile.snapshot.txt), [schemas](20261010T144657Z-priority/schemas.json), [raw results](20261010T144657Z-priority/results.json), [selected cases](20261010T144657Z-priority/selected-cases.json), [oracle updates](20261010T144657Z-priority/oracle-updates.json). Compiler source was not edited.

Expected opening labels were updated **before any opening cases ran**, because the current holder enum introduces `question` for questions without confirmation. The old corpus calls these `unclear`; raw results preserve that old label, while this report applies the predeclared overrides. Questions prefixed by the asks-back style receive `question` too. No observed result was used to choose these overrides.

Five styles are transformations of six base phrasings per selected intent. Bulk `corrects` is a reformulation cue, while boundary controls include actual changed amount/date/intention. Inert test nodes retain fragments; this checks extraction, not production routing, consent invalidation, or bank writes. In pieces cases the last assistant response may change conversational context; inspect per-turn evidence before treating a disagreement as a description defect. Mixed hearing-question plus answer probes are shown separately.

## Coverage

| Stage | Expected intent | Completed / selected | Matches | In words | Pieces | Corrects | Talkative | Asks back | Boundary |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| negotiate | accepts | 32/32 | 32 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 2/2 |
| negotiate | other | 1/1 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/1 |
| negotiate | proposes | 31/31 | 31 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 1/1 |
| negotiate | question | 32/32 | 32 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 2/2 |
| negotiate | too_much | 33/33 | 32 | 6/6 | 5/6 | 6/6 | 6/6 | 6/6 | 3/3 |
| opening | question | 23/23 | 17 | 3/4 | 3/4 | 4/4 | 3/4 | 3/6 | 1/1 |
| opening | unclear | 9/9 | 9 | 2/2 | 2/2 | 2/2 | 2/2 | 0/0 | 1/1 |
| readback | changes | 31/31 | 31 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 1/1 |
| readback | confirms | 30/30 | 30 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 0/0 |
| readback | question | 31/31 | 31 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 1/1 |
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

## Findings and proposed wording

All **258 selected scenarios** completed, with **249/258 final-label agreements**. Eight transient HTTP 502 attempts succeeded on one retry each (266 attempts total); they are not classifier failures. Main pass 768.82 seconds, retry pass 53.54 seconds, excluding the brief inspection gap between them. The full 1,368-case corpus has **not** been completed. These results cover the priority subset against the new snapshot, not the old 39-case run.

| Priority surface | Result | Interpretation |
|---|---:|---|
| Read-back changes / confirmations / questions | 92/92 | Includes all five styles and the explicit “Yes, correct, actually change it to three hundred and fifty.” boundary. No observed final correction-to-confirmation error. This is not a production consent/write-guard test. |
| Negotiation acceptance | 32/32 | Matching offered dates restated in an acceptance remain accepts. |
| Negotiation proposals | 31/31 | Includes “Yes, actually no, I need the twentieth instead.” |
| Negotiation too_much | 32/33 | The two-turn lower-payment request loses its meaning on the second fragment. |
| Negotiation questions | 32/32 | Includes “You tell me what the deadline means.” and “How much did you just say?” |
| Opening | 26/32 | Six disagreements all concern hearing/connection checks, not substantive “who/why” questions or false holder confirmation. |
| Callback boundaries | 4/5 intent labels; 5/5 time checks | Bare “Morning.” becomes other; all explicitly supplied eleven-o'clock cases yield 11:00, without a premature hour on incomplete fragments. |

The remaining disagreement is bare “You tell me.” → question, against the predeclared other label. It is underspecified and should not be called a definite error. Similarly, the six opening hearing-check mismatches expose an underspecified desired convention: the literal description says questions are question, while the model usually treats connection checks as unclear. Neither label should confirm the holder. The report retains the predeclared question oracle, rather than relabeling after observing results.

**Highest-value description change:** the current negotiation schema says “LAST message.” The first fragment “I need a lower amount, but ...” correctly produced too_much and routed to the inert destination; the continuation “… you tell me what it is.” freshly produced question (confidence 0.83548). Suggested wording: “Classify the latest completed meaning. When the latest message explicitly continues an unfinished answer, combine it with the immediately preceding fragment. ‘I need a lower amount, but … / … you tell me what it is’ is too_much. A new standalone information request is question.” The harness retains fragments and the production code may process the first turn earlier, so this does not establish a production payment failure.

**Opening convention:** decide explicitly whether hearing checks should be unclear or question. To preserve the intended distinction between substantive questions and unclear speech, suggested wording: “question means a substantive question about the caller, bank, purpose, or security. Greetings, go-ahead statements, and connection checks such as ‘Can you hear me?’ are unclear. Neither confirms identity.” This would resolve six reported disagreements by defining the policy; it is not a validated change.

**Callback wording:** “gives_time includes availability expressed as a day, clock time, or day part such as morning, when answering the callback question. It does not mean the slot is complete. Never infer an hour from a day part.” This targets the repeatable Morning → other boundary while preserving the successful missing-time behavior.

**Corrections:** no new description change is justified by this sample. Retain the successful current descriptions; if strengthening them, specify that a changed amount/date overrides a retracted yes, while restating the unchanged offer remains confirmation. Do not infer general robustness from these single observations.

No edits were made to `compile.py`. A concurrent compiler change only raised code-node timeout from 15,000 to 40,000 ms; the tested intent descriptions were unchanged ([diff](20261010T144657Z-priority/concurrent-compiler-changes.diff)). The frozen schema remained in use for every initial and retry case. [Earlier 39-case report](20261010T132926Z/README-before-priority-rerun.md) is preserved separately. Failed-attempt call files were archived before retry under `failed-attempts/`; raw results retain every error attempt.


## Reproduce / continue

Continue the frozen snapshot serially (remaining full-corpus cases; original corpus labels require the documented opening adjustment):

```bash
source .env
.venv/bin/python -u scripts/intent_chat_checks.py --resume results/extraction/20261010T144657Z-priority
```

To run a fresh priority sweep against the then-current compiler: `.venv/bin/python -u scripts/intent_priority_sweep.py`.
