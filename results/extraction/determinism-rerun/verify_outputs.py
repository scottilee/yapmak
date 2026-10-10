"""Offline verification of completed extraction outputs; never publishes or simulates."""
from pathlib import Path
import json, sys, collections, hashlib
BASE=Path(__file__).resolve().parent
SNAP=BASE/'snapshot'
sys.path.insert(0,str(SNAP));sys.path.insert(0,str(SNAP/'scripts'));sys.path.insert(0,str(SNAP/'tests'))
import compile as C
from policy import PolicyIR
from check_synthetic_ir import project
from offline_sim import run_case
summary={}
for name in ('a','ab','clean-eom'):
    for i in range(1,4):
        slot=f'det-{name}-{i}'
        p=SNAP/'out'/f'{slot}.policy.json'
        if not p.exists():continue
        ir=PolicyIR.load(str(p));api=SNAP/('tests/fixtures/synthetic/clean-eom-openapi.json' if name=='clean-eom' else 'tools/openapi.json')
        tools=C.parse_openapi(str(api));wf=C.compile_workflow(ir,tools)
        record={'static_errors':C.static_check(wf,tools),'nodes':len(wf['nodes'])}
        prompt=wf['system_prompt']
        record['system_risky_terms']=[word for word in ('recorded','discount','waiver','instalment plan','how much') if word in prompt.lower()]
        record['system_prompt']=prompt
        if name=='clean-eom':
            oracle=json.loads((SNAP/'tests/fixtures/synthetic/clean-eom-expected.json').read_text())
            actual=json.loads(ir.to_json());mismatches=[]
            for field,check in oracle['checks'].items():
                expected=check['expected']
                try:value=project(actual,field)
                except (KeyError,IndexError,StopIteration,TypeError):value={'missing':True}
                if field=='outcomes.$table':expected={k:sorted(v) for k,v in expected.items()}
                if field in ('calendar.holidays','notes.reasons','phrases.prohibited_before_verification'):
                    expected=sorted(expected)
                    if isinstance(value,list):value=sorted(value)
                if expected!=value:mismatches.append({'field':field,'expected':expected,'actual':value})
            record['oracle_checks']=len(oracle['checks']);record['oracle_mismatches']=mismatches
        else:
            cases=[c for c in json.loads((SNAP/'public-test-set.json').read_text()) if c['brief']==('A' if name=='a' else 'B')]
            failures=[]
            for case in cases:
                try:bad,_,_=run_case(wf,case)
                except Exception as e:bad=[repr(e)]
                if bad:failures.append({'case':case['id'],'errors':bad})
            record['offline_cases']=len(cases);record['offline_failures']=failures
        events=[json.loads(x) for x in (SNAP/'traces'/f'{slot}.extract.jsonl').read_text().splitlines()]
        starts={e['session_id'] for e in events if e['event']=='model_session_start'}
        ends={e['session_id'] for e in events if e['event']=='model_session_end'}
        responses=[e for e in events if e['event']=='model_response']
        calls={e['tool_use_id'] for e in events if e['event']=='model_tool_call'}
        decisions={e['tool_use_id'] for e in events if e['event']=='model_tool_permission'}
        record['trace']={'sessions':len(starts),'unpaired_sessions':sorted(starts^ends),'assistant_messages':len(responses),'distinct_message_ids':len({e.get('request_id') for e in responses}), 'messages_missing_id':sum(not e.get('request_id') for e in responses),'tool_calls':len(calls),'unpaired_tool_decisions':sorted(calls^decisions),'denials':[e for e in events if e['event']=='model_tool_permission' and not e['allowed']], 'freya_calls':sum(e['event']=='freya_call' for e in events)}
        summary[slot]=record
(BASE/'output-checks.json').write_text(json.dumps(summary,indent=2))
for slot,r in summary.items():print(slot,{k:v for k,v in r.items() if k not in ('system_prompt','trace')})
