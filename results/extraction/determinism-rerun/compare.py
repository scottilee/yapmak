"""Compare final audited IRs using the frozen PolicyIR defaults; no model calls."""
import sys, json, pathlib, hashlib
BASE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'snapshot'))
from policy import PolicyIR
MISSING={'__missing__':True}
def flatten(v,path='',out=None):
    if out is None: out={}
    if isinstance(v,dict):
        if not v: out[path]={}
        for k,x in sorted(v.items()):
            if k in ('source','unresolved'): continue
            flatten(x,f'{path}.{k}' if path else k,out)
    elif isinstance(v,(list,tuple)):
        key={'special_cases':'name','outcomes.table':'outcome'}.get(path)
        if path=='bands':
            keys=[f'{x["days_late_min"]}..{x["days_late_max"]}' for x in v]
        elif key: keys=[x[key] for x in v]
        else: keys=None
        if keys is not None and len(keys)==len(set(keys)):
            out[path+'.__order__']=keys
            for k,x in zip(keys,v): flatten(x,f'{path}[{k}]',out)
        elif any(isinstance(x,(dict,list,tuple)) for x in v):
            out[path+'.__length__']=len(v)
            for i,x in enumerate(v): flatten(x,f'{path}[{i}]',out)
        else: out[path]=list(v)
    else:out[path]=v
    return out

def differences(ds):
    fs=[flatten(d) for d in ds];out=[]
    for p in sorted(set().union(*(f.keys() for f in fs))):
        vs=[f.get(p,MISSING) for f in fs]
        if len({json.dumps(v,sort_keys=True) for v in vs})>1:out.append({'field':p,'values':vs})
    return out

def cell(v):return '`'+json.dumps(v,ensure_ascii=False,sort_keys=True).replace('|','\\|').replace('`','&#96;')+'`'
summary={};lines=['# Extraction determinism — three audited runs per input','',(BASE/'findings.md').read_text(),'',
'Nine fresh extraction runs with the same frozen source and inputs; no simulations or publication. Each run includes the extractor’s independent audit and any validation-triggered repair. Source hashes are in [manifest.json](determinism-rerun/manifest.json); raw policies, audits, and model traces are under [snapshot](determinism-rerun/snapshot/).','',
'Comparison excludes every `source` span and unresolved free text/provenance. Diagnostic unresolved topic labels are reported separately below, outside the policy-difference counts. All other values, including wording, are compared. Effective comparisons apply the frozen `PolicyIR` defaults. Special cases are aligned by name, outcomes by outcome, and bands by range; their original order is compared separately. Other lists retain their order. `<missing>` is represented as `{"__missing__": true}`. Raw-only differences are also reported so omitted defaults are not hidden.','']
for name in ('a','ab','clean-eom'):
    slots=[f'det-{name}-{i}' for i in range(1,4)]
    runs=[json.loads((BASE/f'{s}.run.json').read_text()) for s in slots]
    raw=[json.loads((BASE/'snapshot/out'/f'{s}.policy.json').read_text()) for s in slots]
    effective=[PolicyIR.from_dict(d).to_dict() for d in raw]
    dif=differences(effective);rawdiff=differences(raw)
    effectivepaths={x['field'] for x in dif};rawonly=[x for x in rawdiff if x['field'] not in effectivepaths]
    costs=[];purposes=[]
    for slot in slots:
        events=[json.loads(l) for l in (BASE/'snapshot/traces'/f'{slot}.extract.jsonl').read_text().splitlines()]
        calls=[e for e in events if e.get('event')=='model_session_end']
        costs.append(sum(e.get('cost_usd',0) or 0 for e in calls));purposes.append([e.get('purpose') for e in calls])
    summary[name]={'runs':runs,'costs':costs,'passes':purposes,'effective_differences':dif,'raw_only_differences':rawonly}
    lines += [f'## {name}','',f'{len(dif)} effective field differences; {len(rawonly)} additional raw-only differences.','', '| Run | Exit | Seconds | Reported model cost | Passes |','|---|---:|---:|---:|---|']
    for i,r in enumerate(runs):lines.append(f'| [{slots[i]}](determinism-rerun/{slots[i]}.log) | {r["exit_code"]} | {r["duration_s"]} | ${costs[i]:.4f} | {", ".join(purposes[i])} |')
    for title,rows in [('Effective fields',dif),('Raw-only fields (effective values agree)',rawonly)]:
        lines += ['',f'### {title}','','| Field | Run 1 | Run 2 | Run 3 |','|---|---|---|---|']
        lines += ['| '+cell(r['field'])+' | '+' | '.join(cell(v) for v in r['values'])+' |' for r in rows]
        if not rows:lines.append('| None | — | — | — |')
lines += ['', '## Diagnostic unresolved topic labels', '', 'These labels are model-authored diagnostic identifiers, not operative rules. Text and provenance are excluded; sorting removes incidental order. They are not included in the policy-field totals.', '', '| Input | Run 1 topics | Run 2 topics | Run 3 topics |', '|---|---|---|---|']
for name in summary:
    topics=[]
    for i in range(1,4):
        d=json.loads((BASE/'snapshot/out'/f'det-{name}-{i}.policy.json').read_text())
        topics.append(sorted(x.get('topic','') for x in d.get('unresolved',[])))
    summary[name]['unresolved_topics']=topics
    lines.append('| '+name+' | '+' | '.join(cell(x) for x in topics)+' |')
manifest=json.loads((BASE/'manifest.json').read_text())
assert all(hashlib.sha256((BASE/'snapshot'/p).read_bytes()).hexdigest()==h for p,h in manifest.items()),'snapshot changed'
(BASE/'comparison.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
(BASE.parent/'determinism.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:{'effective':len(v['effective_differences']),'raw_only':len(v['raw_only_differences']),'cost':sum(v['costs'])} for k,v in summary.items()},indent=2))
