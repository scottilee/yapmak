"""Chat-only priority rerun; frozen schemas, concurrent isolated calls per stage."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
import intent_chat_checks as checks


def main():
    out=checks.ROOT/'results/extraction'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-priority')
    out.mkdir(parents=True)
    before=(checks.ROOT/'compile.py').read_bytes()
    checks.snapshot(out)
    assert before==(out/'compile.snapshot.txt').read_bytes(), 'Compiler changed during snapshot; restart before testing'
    cases=json.loads((out/'cases.json').read_text())
    wanted={'negotiate':{'question','too_much','accepts','proposes'},'readback':{'changes','confirms','question'},'opening':{'unclear'}}
    selected=[c for c in cases if c['style']=='boundary' or c['expected'] in wanted.get(c['group'],set())]
    checks.save_json(out/'selected-cases.json',selected)
    meta=json.loads((out/'metadata.json').read_text());meta.update(concurrency=4,selected_count=len(selected),selection='All boundary controls plus 30/style-balanced cases each for negotiate question/too_much/accepts/proposes, readback changes/confirms/question, and opening unclear.',method='Chat-only; unmodified frozen extraction schemas; four concurrent isolated calls per stage; sequential publication to runtime-check; no bank actions.')
    checks.save_json(out/'metadata.json',meta)
    schemas=json.loads((out/'schemas.json').read_text())
    holder=next(e for e in schemas['opening']['extraction_schema'] if e['name']=='holder')
    overrides={c['id']:{'original_expected':c['expected'],'expected':'question','reason':'Current holder enum distinguishes questions from unclear speech.'} for c in selected if c['group']=='opening' and any('?' in t for t in c['turns'])} if 'question' in holder['enum_values'] else {}
    checks.save_json(out/'oracle-updates.json',{'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before_opening_execution':True,'overrides':overrides})
    print('ARTIFACTS',out,'SELECTED',len(selected),flush=True)
    results=[];start=time.monotonic()
    for group in ['negotiate','readback','opening','third_party']:
        subset=[c for c in selected if c['group']==group]
        if not subset:continue
        pub=out/('published-'+group);pub.mkdir(exist_ok=True)
        schemas=json.loads((out/'schemas.json').read_text())
        ids=checks.publish(checks.workflow(group,schemas[group]),pub)
        errors=0
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            # Batches bound outstanding work during an outage; never republish with active calls.
            for offset in range(0,len(subset),4):
                futures=[pool.submit(checks.run_case,ids,c,out) for c in subset[offset:offset+4]]
                for f in concurrent.futures.as_completed(futures):
                    r=f.result();results.append(r);checks.save_json(out/'results.json',results)
                    errors=errors+1 if r['status']!='completed' else 0
                    print(json.dumps({k:r[k] for k in ('id','status','expected','actual','passed','duration_s','error') if k in r}),flush=True)
                if errors>=4:
                    print('PAUSED infrastructure errors; evidence preserved',flush=True);return
    checks.save_json(out/'completion.json',{'duration_s':round(time.monotonic()-start,2),'completed':sum(r['status']=='completed' for r in results),'attempts':len(results),'selected':len(selected)})
    print('FINISHED',out,flush=True)

if __name__=='__main__':main()
