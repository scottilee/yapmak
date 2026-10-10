"""Compare extracted IR with the independently authored synthetic brief oracle."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import policy


def project(ir, path):
    if path == 'identity.requirements.$fields':
        return [v['field'] for v in ir['identity']['requirements']]
    if path == 'outcomes.$table':
        return {r['outcome']:sorted(r['reasons']) for r in ir['outcomes']['table']}
    if path == 'bands.$rules':
        return [{k:v[k] for k in ('days_late_min','days_late_max','deadline','attempts')} for v in sorted(ir['bands'],key=lambda x:x['days_late_min'])]
    value = ir
    parts = path.split('.')
    if parts[0] == 'special_cases':
        value = next(v for v in ir['special_cases'] if v['name']==parts[1])
        parts = parts[2:]
    for part in parts:
        value = value[int(part)] if isinstance(value,list) else value[part]
    return value


def unknown_keys(raw, normalized, path=''):
    errors=[]
    if isinstance(raw,dict) and isinstance(normalized,dict):
        for k,v in raw.items():
            here=(path+'.'+k).lstrip('.')
            if k not in normalized:
                errors.append({'path':here,'value':v,'issue':'Raw JSON key discarded during PolicyIR loading'})
            else:
                errors.extend(unknown_keys(v,normalized[k],here))
    elif isinstance(raw,list) and isinstance(normalized,list):
        for i,(a,b) in enumerate(zip(raw,normalized)):
            errors.extend(unknown_keys(a,b,f'{path}.{i}'))
    return errors


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('fixture')
    ap.add_argument('policy_path',type=Path)
    ap.add_argument('out',type=Path)
    args=ap.parse_args()
    expected=json.loads((ROOT/'tests/fixtures/synthetic'/(args.fixture+'-expected.json')).read_text())
    raw=json.loads(args.policy_path.read_text())
    ir=policy.PolicyIR.from_dict(raw).to_dict()
    # Normalize dataclass tuples to JSON lists, without hiding missing raw fields.
    ir=json.loads(json.dumps(ir))
    rows=[]
    for path,item in expected['checks'].items():
        want=item['expected']
        try:
            actual=project(ir,path)
        except (KeyError,IndexError,StopIteration,TypeError):
            actual={'missing':True}
        if path=='outcomes.$table':
            want={k:sorted(v) for k,v in want.items()}
        if path in ('calendar.holidays','notes.reasons','phrases.prohibited_before_verification'):
            want=sorted(want)
            if isinstance(actual,list): actual=sorted(actual)
        rows.append(dict(path=path,expected=want,actual=actual,match=want==actual,source=item['source']))
    audit_path=args.policy_path.with_name(args.policy_path.name.replace('.policy.json','.audit.json'))
    audit=json.loads(audit_path.read_text()) if audit_path.exists() else {}
    report=dict(fixture=args.fixture,checks=rows,mismatches=[r for r in rows if not r['match']],
                raw_unknown_keys=unknown_keys(raw,ir),unresolved=ir.get('unresolved',[]),
                audit_unresolved=audit.get('unresolved',[]),audit_fixed=audit.get('fixed',[]),
                source_docs=ir.get('source_docs'),notes=expected['comparison_notes'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(checks=len(rows),matches=sum(r['match'] for r in rows),mismatches=report['mismatches'],
        unresolved=report['unresolved'],audit_unresolved=report['audit_unresolved'],raw_unknown_keys=report['raw_unknown_keys']),indent=2))


if __name__=='__main__':
    main()
