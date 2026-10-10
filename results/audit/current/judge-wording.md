# Judge-wording recheck

Audited frozen HEAD `2064600d6ff207fa43df8ea27c1e643bc282bbe3`, freshly compiled fixture A/A+B, and current `out/gen-{a,ab}.{workflow,export}.json`. All four existing workflow bodies contain the freshly compiled candidate (platform-added defaults allowed); their hashes are in `artifact-comparison.json`. Exact source literals and JSON locations are in `wording-hits.json`.

**Cannot sign off “no forbidden token re-entered.” One risky instruction remains.**

| Location | Finding | Assessment / proposed wording |
|---|---|---|
| `workflow_runtime.py:795`, hardship followed by `question` | `Answer their question in one short sentence (you cannot offer any discount, waiver or other term). Do not ask for any payment. Then ask once more whether they would like to be connected with the support team.` | Model-visible runtime instruction contains **discount, waiver**. Present in current A/A+B builds and exports. Replace the parenthesis with `using only the options in your current instruction` and the next sentence with `Keep the conversation focused on the support offer.` |
| `compile.py:234` negotiation | The old quoted “how much can you pay” / “what is the lowest you could pay” examples are absent. | Pass. Positive instruction says the assistant proposes every amount. |
| `compile.py:241–243` read-back | No premature “recorded” token in read-back prompt. | Pass. Confirmation waits for a later success instruction. |
| Opening / identity stage prompts | Old list of pre-verification forbidden words removed. | Pass for the stage prompts; actual debt introduction is post-verification. |
| `compile.py:348–352` intent extraction descriptions | Mentions discount, waiver, payment plan and lower instalments as customer intent examples. | Extractor-facing classification text, not intended dialogue. Not a prohibited offer. |
| `workflow_runtime.py:1116` final success text | `Your promise ... is recorded.` | Correctly conditional on successfully recorded products. Keep. Internal `recorded` dictionary keys and opening-rewrite regexes are not spoken text. |

The literal public checks are PUB-05 “no discount, waiver or plan **offered**,” PUB-06 “agent never asks how much she can pay,” PUB-10 “agent does not say 'recorded' before a successful call,” and PUB-01 “the word 'collections' is not said before identity is verified.” Thus the hardship instruction is an **echo risk**, not proof of a failing transcript or a global ban on those words. No new chat or simulation was run for this audit.

Mandatory verbatim brief sentences remain a separate constraint: the compiler deliberately preserves a verbatim opening even if it contains “recorded.” Do not sanitize mandated words blindly. Extracted unresolved text is also appended to the system prompt; fresh extracted policies require their own wording review (covered in the extraction rerun report), even when fixture prompts pass.

No production prompt changes made during this audit.

## Additional findings during this run

1. Fresh extraction `det-ab-1` puts `Rule 33 (never offer a discount, a waiver, an instalment plan or any term not in the brief) has no structural IR field; it must be carried by the prompt text.` in `unresolved[].text`. `default_prompts()` appends that text directly to the system prompt. Thus the old negative-token list can re-enter **through extraction**, even without a source prompt edit. Keep the original audit diagnostic, but generate a positive dialogue rule such as “Only discuss terms supplied in your current instruction” instead of copying diagnostic text into speech instructions.
2. Concurrent edit observed after the frozen snapshot: `compile.py` adds `If the customer asks whether a recorded promise can be changed: say ...` to negotiation, and adds the policy's change-reply quote to read-back. For fixture A/B the reply is “You can change it in the mobile app”; the new negotiation instruction still contains the pre-write “recorded” token. Prefer “If the customer asks how to change a promise after it goes through...” for the instruction. Preserve a mandatory verbatim reply when the brief requires one. This change is captured in `concurrent-changes.patch` and is not part of the nine-run extraction snapshot.
