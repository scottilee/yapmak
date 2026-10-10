"""Report the current-schema priority chat sweep; no remote calls."""
import collections
import hashlib
import json
from pathlib import Path
import sys
from report_intent_checks import current_extractions

run=Path(sys.argv[1]);meta=json.loads((run/'metadata.json').read_text())
raw=json.loads((run/'results.json').read_text());planned=json.loads((run/'selected-cases.json').read_text())
ov=json.loads((run/'oracle-updates.json').read_text())['overrides'] if (run/'oracle-updates.json').exists() else {}
def expected(r):return ov.get(r['id'],{}).get('expected',r['expected'])
def mixed(r):return bool(r.get('ambiguity'))
def cell(v):return str(v).replace('|','\\|').replace('\n',' ')
completed={r['id']:dict(r,evaluated_expected=expected(r),evaluated_passed=r['actual']==expected(r)) for r in raw if r['status']=='completed'}
errors=[r for r in raw if r['status']!='completed'];bad=[r for r in completed.values() if not r['evaluated_passed']];strict=[r for r in completed.values() if not mixed(r)]
lines=['# Current-schema priority intent sweep','',f'Run `{run.name}`: **{len(completed)}/{len(planned)} selected scenarios completed** from the 1,368-scenario corpus. **{sum(r["evaluated_passed"] for r in strict)}/{len(strict)} clear-oracle matches**; {len(bad)} total disagreements, including {sum(mixed(r) for r in bad)} mixed/underspecified cases. {len(errors)} infrastructure-error attempts. These are single observations, not consistency estimates.','',
'Fresh schema snapshot; results from the old 39-case run are not pooled. Four concurrent isolated calls per stage on `runtime-check`; publication is sequential between stages. Only chat routes, with inert destinations and no bank tools or simulations. Negotiation/read-back context is 420 on Friday 16 October 2026, `now=2026-10-14T11:00`.','',
f'Compiler SHA-256: `{meta["compile_sha256"]}`. [Snapshot]({run.name}/compile.snapshot.txt), [schemas]({run.name}/schemas.json), [raw results]({run.name}/results.json), [selected cases]({run.name}/selected-cases.json), [oracle updates]({run.name}/oracle-updates.json). Compiler source was not edited.','',
'Expected opening labels were updated **before any opening cases ran**, because the current holder enum introduces `question` for questions without confirmation. The old corpus calls these `unclear`; raw results preserve that old label, while this report applies the predeclared overrides. Questions prefixed by the asks-back style receive `question` too. No observed result was used to choose these overrides.','',
'Five styles are transformations of six base phrasings per selected intent. Bulk `corrects` is a reformulation cue, while boundary controls include actual changed amount/date/intention. Inert test nodes retain fragments; this checks extraction, not production routing, consent invalidation, or bank writes. In pieces cases the last assistant response may change conversational context; inspect per-turn evidence before treating a disagreement as a description defect. Mixed hearing-question plus answer probes are shown separately.','',
'## Coverage','', '| Stage | Expected intent | Completed / selected | Matches | In words | Pieces | Corrects | Talkative | Asks back | Boundary |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for group,intent in sorted({(r['group'],expected(r)) for r in planned}):
 cs=[r for r in planned if r['group']==group and expected(r)==intent];rs=[completed[r['id']] for r in cs if r['id'] in completed]
 row=[group,intent,f'{len(rs)}/{len(cs)}',sum(r['evaluated_passed'] for r in rs)]
 for style in ('in_words','pieces','corrects','talkative','asks_back','boundary'):
  ss=[r for r in rs if r['style']==style];row.append(f'{sum(r["evaluated_passed"] for r in ss)}/{len(ss)}')
 lines.append('| '+' | '.join(map(cell,row))+' |')
lines+=['','## Exact disagreements','','| Case / evidence | Utterance(s) | Expected | Actual | Last-turn extraction | Assessment |','|---|---|---|---|---|---|']
for r in bad:
 call=json.loads((run/'calls'/(r['id']+'.call.json')).read_text());events=[e for e in current_extractions(call,r['turns'][-1]) if e['name']==r['variable']]
 fresh=', '.join(str(e['value'])+' @ '+str(e['confidence']) for e in events) or 'none; retained/missing'
 lines.append('| '+' | '.join(map(cell,[f'[{r["id"]}]({run.name}/calls/{r["id"]}.turns.json)',' → '.join(r['turns']),r['evaluated_expected'],r['actual'],fresh,'mixed/underspecified' if mixed(r) else 'clear-oracle disagreement']))+' |')
lines+=['','## Boundary controls','','| Case | Utterance(s) | Expected → actual | Callback clock check |','|---|---|---|---|']
for c in planned:
 if c['style']!='boundary':continue
 r=completed.get(c['id']);lines.append('| '+' | '.join(map(cell,[c['id'],' → '.join(c['turns']),f'{expected(c)} → {r["actual"] if r else "pending"}',f'{r.get("actual_time")!r}; pass={r.get("time_passed")}' if r and 'expected_time' in c else '—']))+' |')
if (run/'findings.md').exists():lines+=['',(run/'findings.md').read_text()]
lines+=['','## Reproduce / continue','','Continue the frozen snapshot serially (remaining full-corpus cases; original corpus labels require the documented opening adjustment):','','```bash',f'source .env',f'.venv/bin/python -u scripts/intent_chat_checks.py --resume results/extraction/{run.name}', '```','', 'To run a fresh priority sweep against the then-current compiler: `.venv/bin/python -u scripts/intent_priority_sweep.py`.','']
(run/'evaluated-results.json').write_text(json.dumps(list(completed.values()),indent=2))
(run.parent/'README.md').write_text('\n'.join(lines))
print(json.dumps({'completed':len(completed),'selected':len(planned),'clear_matches':sum(r['evaluated_passed'] for r in strict),'clear_total':len(strict),'disagreements':len(bad),'infrastructure_errors':len(errors)}))
