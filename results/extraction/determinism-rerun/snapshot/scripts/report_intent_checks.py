"""Render intent chat evidence; does not call Freya or change compiler code."""
import argparse
from collections import Counter
import json
from pathlib import Path


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def current_extractions(call, utterance):
    messages = call.get('messages', [])
    start = max((i for i, m in enumerate(messages) if m.get('role') == 'user'), default=0)
    events = []
    for m in messages[start:]:
        try:
            event = json.loads(m.get('message', ''))
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict) and event.get('event') == 'variable_extracted':
            events.append({k:event.get(k) for k in ('name','value','confidence','input_text','source_node','raw_response')})
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    args = ap.parse_args()
    run = args.run
    meta = json.loads((run / 'metadata.json').read_text())
    cases = json.loads((run / 'cases.json').read_text())
    results = json.loads((run / 'results.json').read_text())
    completed = {r['id']:r for r in results if r['status']=='completed'}
    errors = [r for r in results if r['status']!='completed']
    mismatches = [r for r in completed.values() if not r['passed']]
    mixed = lambda r: bool(r.get('ambiguity')) or r['style']=='asks_back'
    strict = [r for r in completed.values() if not mixed(r)]
    lines = ['# Freya intent extraction chat checks', '',
        f"Run: `{run.name}`. **{len(completed)}/{len(cases)} scenarios completed**; {len(errors)} infrastructure-error attempts (not classification failures). "
        f"{len(mismatches)} final-label disagreements, including {sum(mixed(r) for r in mismatches)} ambiguous/mixed-question probes. "
        f"Clear-oracle agreement: {sum(r['passed'] for r in strict)}/{len(strict)}. These are single observations, not three-run consistency scores.", '',
        ('**Coverage is incomplete: the requested approximately thirty live phrasings per intent have not been achieved.** The prepared corpus is not evidence of execution. Repeated HTTP 502/503/504 failures interrupted serial batches; each batch stops after three consecutive infrastructure errors.' if len(completed) < len(cases) else 'All prepared scenarios completed; see per-value and per-style coverage below.'), '',
        ('**Concurrent source change:** `compile.py` changed while the frozen-schema run was in progress. The newer identity enum adds `question`, and read-back descriptions were expanded; those revisions were not tested. [Recorded diff]('+run.name+'/concurrent-compiler-changes.diff). This task made no edits to `compile.py`.' if (run/'concurrent-compiler-changes.diff').exists() else 'No concurrent-source comparison is recorded for this run.'), '',
        '## Method and limits', '',
        f"- Used only `POST /api/v2/chat/message` on `runtime-check`, with one isolated call per scenario, a greeting to establish the assistant question, and explicit chat end. No simulations or bank calls.",
        f"- Snapshot SHA-256: `{meta['compile_sha256']}`. [Compiler snapshot]("+run.name+'/compile.snapshot.txt); [exact schemas]('+run.name+'/schemas.json); [cases]('+run.name+'/cases.json); [raw results]('+run.name+'/results.json). The compiler source was not edited.',
        '- Copied complete extraction schemas, enum values, confidence thresholds, and enum transition conditions from the compiled Brief A fixture. Test conversations use fixed stage questions and inert destinations instead of production actions. This isolates extraction; it does not demonstrate production state handling, bank writes, or end-to-end routing.',
        '- Thirty scenarios per semantic value: six base phrasings in each of `in_words`, `pieces`, `corrects`, `talkative`, and `asks_back`, plus boundary controls. These are style transformations of six base phrasings, not thirty independent paraphrases. `none` is a reset sentinel, not a customer intent.',
        '- `pieces` uses separate chat turns. The bulk `corrects` style uses a reformulation cue; boundary probes include actual changed values/intents. `asks_back` adds a hearing question before the substantive answer and is reported separately because the existing descriptions do not define mixed-intent precedence.',
        '- Expected labels were recorded before testing. Ambiguous bare “You tell me” is not counted as a clear error. A final label alone may reflect retained state; the disagreement table records whether the last turn actually extracted it.',
        '- The fixed negotiation offer/read-back is 420 on Friday 16 October 2026; simulated `now` is 14 October at 11:00. Callback questions ask for both day and time. Missing hours must not become invented callback times.', '',
        '## Observed boundaries', '',
        *([
        '- Bare callback answer **“Morning.” → `other`**, while the expected availability label was `gives_time`. The clock time correctly stayed empty. The description currently specifies a day and/or time without explicitly including day parts; make that intent/completeness distinction explicit. A greeting interpretation is possible, so retain the preceding callback question when reproducing it.',
        '- **“You tell me.” → `question`**; this is underspecified, not proof of a classifier defect. After that, **“What is the smallest amount I can pay?” → `too_much`**. **“You tell me what the deadline means.” → `question`** and **“Can you offer a smaller payment?” → `too_much`** also matched.',
        '- **“Yes, I can pay on Friday the sixteenth.”** and **“Friday the sixteenth, yes, that works.”** both became `accepts` for the matching offer. **“Yes, actually no, I need the twentieth instead.” → `proposes`**.',
        '- Read-back: **“Yes, correct, actually change it to three hundred and fifty.” → `changes`**; **“Do you mean this Friday or next Friday?” → `question`**. These are isolated intent observations, not consent/write-guard validation.',
        '- Callback **“Tomorrow morning.” → “Around eleven.”**, **“Tomorrow.” → “In the morning.” → “Around eleven.”**, and **“Tomorrow around...” → “...eleven in the morning.”** ended at `gives_time`, `11:00`; no hour appeared before the final fragment. This harness retains extraction state; it does not exercise the production callback code’s clearing/reassembly behavior.',
        '- Opening: **“Who is calling?”** and **“Go on, I am listening.”** both became `unclear`.', '',
        ] if all(f'boundary-{i:02d}' in completed for i in range(1,19)) else ['Boundary checks are incomplete; use the per-case evidence table below.', '']),
        '## Coverage and final intent labels', '',
        '| Context | Expected intent | Completed / target | Exact matches | In words | Pieces | Corrects | Talkative | Asks back |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    groups = dict.fromkeys((c['group'],c['expected']) for c in cases if c['style']!='boundary')
    for group, intent in groups:
        planned = [c for c in cases if c['group']==group and c['expected']==intent and c['style']!='boundary']
        done = [completed[c['id']] for c in planned if c['id'] in completed]
        row = [group,intent,f'{len(done)} / {len(planned)}',str(sum(r['passed'] for r in done))]
        for style in ('in_words','pieces','corrects','talkative','asks_back'):
            subset = [r for r in done if r['style']==style]
            row.append(f"{sum(r['passed'] for r in subset)}/{len(subset)}")
        lines.append('| '+' | '.join(row)+' |')
    lines += ['', '## Exact final-label disagreements', '',
        'Turns are separated with **→**. Expected means the predeclared desired interpretation; mixed/underspecified rows require a precedence decision before being called defects.', '',
        '| Case / evidence | Style | Exact utterance(s) | Expected | Observed | Last-turn extraction | Assessment |',
        '|---|---|---|---|---|---|---|']
    annotated = []
    for r in mismatches:
        path = run/'calls'/(r['id']+'.call.json')
        extracted = current_extractions(json.loads(path.read_text()),r['turns'][-1]) if path.exists() else []
        intent_events = [e for e in extracted if e['name']==r['variable']]
        fresh = ', '.join(str(e['value'])+' @ '+str(e['confidence']) for e in intent_events) or 'none; retained/missing'
        assessment = 'mixed/underspecified' if mixed(r) else 'label mismatch'
        annotated.append(dict(id=r['id'], final_turn_extractions=extracted, assessment=assessment))
        lines.append('| '+' | '.join(cell(x) for x in [f"[{r['id']}]({run.name}/calls/{r['id']}.turns.json)",r['style'],' → '.join('“'+t+'”' for t in r['turns']),r['expected'],r.get('actual'),fresh,assessment])+' |')
    if not mismatches:
        lines.append('| — | — | No completed-case disagreements yet | — | — | — | — |')
    lines += ['', '## Boundary controls', '',
        '| Case | Context | Exact utterance(s) | Expected → observed | Callback time expected → observed |',
        '|---|---|---|---|---|']
    for c in cases:
        if c['style']!='boundary':
            continue
        r=completed.get(c['id'])
        observed = r.get('actual') if r else 'pending / infrastructure error'
        cb = f"{c.get('expected_time')!r} → {r.get('actual_time')!r}; time check={r.get('time_passed')}" if r and 'expected_time' in c else '—'
        lines.append('| '+' | '.join(cell(x) for x in [c['id'],c['group'],' → '.join(c['turns']),f"{c['expected']} → {observed}",cb])+' |')
    lines += ['', '## Proposed description wording (not applied or validated)', '',
        'These are candidate replacements/clarifications for review. Changing a description can shift other classes; repeat the same corpus after any change before treating it as an improvement.', '',
        '| Field | Proposed wording | Purpose |', '|---|---|---|',
        '| `cust_intent` — questions and unclear speech | “`question` means a substantive information request that does not express a more specific payment/special-case intent. A request for a lower payment is `too_much`, even when phrased as a question. Greetings, noise, waiting, and an unfinished or uninterpretable fragment are `other`. Bare ‘you tell me’ needs context; do not infer inability to pay from those words alone.” | Separate generic questions, requests to reduce an amount, and insufficient evidence. |',
        '| `cust_intent` — acceptance/proposal | “`accepts` means agreement to the current offer, including repeating its same amount and/or date. Repeating the offered date does not make it `proposes`. `proposes` means a different or newly volunteered amount/date. `pays_today` means an explicit commitment to pay today/now; merely asking about today is not commitment.” | Remove overlap between accepts and any mention of a date/amount. |',
        '| All intent fields — corrections/mixed speech | “Classify the final intended meaning after explicit corrections; disregard a retracted yes/no or replaced value. A hearing/check-back question does not override an otherwise explicit substantive answer. A substantive question with no clear agreement must never become confirmation.” | Define correction and incidental-question precedence. Apply policy-specific special-case precedence separately. |',
        '| `holder` / `id_intent` | “At the holder check, ‘hello’, ‘go ahead’, ‘I am listening’, and questions are `unclear`, not identity confirmation. For the newer identity enum observed during this run, ordinary questions about purpose/security/robots/scams are `question`; `asks_purpose` requires explicitly withholding an answer until told the purpose. A request to repeat or a hearing problem must not count as a refusal. The frozen older identity enum did not have `question`; do not apply this wording to it without the corresponding enum update. Giving only part of the requested security answer is `answers`, not completion.” | Respect context-specific enums; there is no universal question/unclear value. |',
        '| `tp_intent` | “`gives_time` means any availability information: a day, a clock time, or a part of day such as ‘morning’. It does not imply a complete schedulable slot. ‘Tomorrow morning’ followed by ‘around eleven’ is a continuation of the same availability answer. `cannot_say` means explicit inability to provide availability; silence or an unfinished fragment is `other`.” | Keep intent distinct from callback completeness. |',
        '| `cb_time` | “Extract only an explicitly stated clock time. ‘Morning’ or ‘afternoon’ alone leaves the time empty. ‘Around eleven in the morning’ is `11:00`. A continuation may use the immediately preceding part-of-day context, but never invent an hour from a day part. A correction replaces the earlier hour.” | Avoid guessed callback hours and clarify multi-turn pieces. |',
        '| `rb_intent` | “`confirms` means explicit agreement to the unchanged read-back, including repeating the same amount/date. Any changed amount/date is `changes`, even after ‘yes’ or ‘correct’. A question without unqualified agreement is `question`. An incomplete correction is not confirmation; request completion.” | Prevent stale or premature consent. |', '',
        '## Infrastructure and reproducibility', '',
        f"{len(errors)} infrastructure-error attempts were excluded from classifier denominators. Raw error details remain in results.json; retries retain the original attempt. Completed calls and per-turn variables are under `{run.name}/calls/`.", '',
        'Resume the snapshot with:', '', '```bash', 'source .env',
        f'.venv/bin/python -u scripts/intent_chat_checks.py --resume results/extraction/{run.name}',
        f'.venv/bin/python scripts/report_intent_checks.py results/extraction/{run.name}', '```', '']
    (run.parent/'README.md').write_text('\n'.join(lines))
    (run/'disagreement-analysis.json').write_text(json.dumps(annotated,indent=2))
    print(f'Report: {len(completed)}/{len(cases)} completed; {len(mismatches)} disagreements; {len(errors)} infrastructure errors')


if __name__=='__main__':
    main()
