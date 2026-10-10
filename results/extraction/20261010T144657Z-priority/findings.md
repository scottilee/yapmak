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
