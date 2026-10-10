"""Identity hint and bounded promise retries via chat; no simulations.

PUB-10 fails once then succeeds. A separate deliberate unknown-product request
checks retry exhaustion without claiming the mock supports two service outages.
"""
import argparse
import datetime
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts'),str(ROOT/'tools')]
import freya
from scripts.chatlib import events as chat_events
from score import http
from runtime_checks import publish, route, conversation, code_node, save_json, variables_from
from extraction_checks import capture, source_adapter
SPEC=json.loads((ROOT/'tools/openapi.json').read_text())
SCHEMAS=json.loads((ROOT/'tests/fixtures/extraction_schemas.json').read_text())['schemas']
CASES={c['id']:c for c in json.loads((ROOT/'public-test-set.json').read_text())}


def api_node(name, operation, bindings, transitions, mappings):
    original=SPEC['paths']['/'+operation]['post']['requestBody']['content']['application/json']['schema']
    body=json.loads(json.dumps(original))
    body['properties']={key:dict(value,default=bindings[key]) for key,value in body['properties'].items() if key in bindings}
    tool={'type':'function','config':{'maxRetries':0,'timeoutMs':10000},'function':{'name':operation,'handler':'__function__:api_call','parameters':{'type':'object','properties':{
        'url':{'type':'string','default':SPEC['servers'][0]['url']+'/'+operation},'method':{'type':'string','default':'POST'},
        'headers':{'type':'object','properties':{'Content-Type':{'type':'string','default':'application/json'}}},'body':body}}}}
    return dict(name=name,node_type='api_request',passthrough=True,on_enter={'type':'silent'},passthrough_default_transition=transitions[-1]['target_node'],
                pre_actions=[tool],response_mapping=[dict(path='data.'+key,variable=value) for key,value in mappings.items()],transitions=transitions)


def checked_code(name, source, transitions):
    node=code_node(source,transitions);node['name']=name;return node


def tool_events(call):
    return [event for event in chat_events(call) if event['event'] in ('function_call_start', 'function_call_complete')]


def hint(out):
    session=http('/v1/practice/sessions',{'case':'PUB-11'})
    variables=session['variables'];variables.update(identity_hint='',identity_normalized='',identity_status='absent')
    normalize=source_adapter('identity_date')+"\nvars['identity_status'] = 'absent'\n"
    nodes=dict(
        collect=conversation('collect','Ask for date of birth. If the last hint is day_month_swapped, ask the caller to say the month as a word. Last hint: {{identity_hint}}. Do not disclose account information.',SCHEMAS['identity_date'],[route('normalize','identity_status','complete')]),
        normalize=checked_code('normalize',normalize,[route('collect','identity_normalized','unreadable'),route('verify')]),
        verify=api_node('verify','verify_identity',dict(customer_id='{{customer_id}}',field='date_of_birth',answer='{{identity_normalized}}'),
            [route('verified','identity_verified','true'),route('verified','identity_verified','True'),route('collect')],
            dict(ok='identity_ok',verified='identity_verified',hint='identity_hint',wrong_answers_left='wrong_answers_left')),
        verified=conversation('verified','Say the date-of-birth answer passed. Do not say full identity is verified; the phone check has not run.'))
    ids=publish(dict(initial_node='collect',system_prompt='You are a synthetic identity test assistant.',nodes=nodes),out)
    records=capture(ids,variables,['Hello.','06/03/1987.','The third of June nineteen eighty-seven.'],out,'hint')
    ledger=http('/v1/practice/ledger/'+variables['customer_id']);save_json(out/'hint.ledger.json',ledger)
    calls=[c for c in ledger['calls'] if c['tool']=='verify_identity']
    report=dict(calls=calls,first_vars={k:v for k,v in records[1]['values'].items() if k.startswith('identity_') or k=='wrong_answers_left'},
                final_vars={k:v for k,v in records[2]['values'].items() if k.startswith('identity_') or k=='wrong_answers_left'})
    report['passed']=len(calls)==2 and calls[0]['result'].get('hint')=='day_month_swapped' and calls[0]['result'].get('wrong_answers_left')==3 and calls[1]['result'].get('verified') is True
    save_json(out/'summary.json',report);print(json.dumps(report,indent=2),flush=True)


def retry(out):
    init="""vars['write_attempts'] = 1
vars['bank_ok_history'] = ''
vars['bank_ok'] = 'pending'
vars['write_decision'] = 'pending'
vars['consent_action'] = 'pending'
"""
    evaluate="""ok = str(vars.get('bank_ok', '')).lower()
vars['bank_ok_history'] = str(vars.get('bank_ok_history', '')) + ok + ','
vars['write_decision'] = 'service_error'
try:
    attempts = int(vars.get('write_attempts', 0))
    if ok == 'true':
        vars['write_decision'] = 'recorded'
    elif attempts < 2:
        vars['write_attempts'] = attempts + 1
        vars['write_decision'] = 'retry'
        vars['bank_ok'] = 'pending'
except Exception:
    vars['write_decision'] = 'service_error'
"""
    nodes=dict(
        readback=conversation('readback','Read back {{amount}} dollars on {{date}} for the credit card. Ask Do you confirm?',SCHEMAS['consent'],[route('init','consent_action','confirm')]),
        init=checked_code('init',init,[route('write')]),
        write=api_node('write','create_promise',{k:'{{'+k+'}}' for k in ('customer_id','product_id','amount','date')},[route('evaluate')],dict(ok='bank_ok',error='bank_error',promise_id='promise_id')),
        evaluate=checked_code('evaluate',evaluate,[route('success','write_decision','recorded'),route('write','write_decision','retry'),route('failed')]),
        success=conversation('success','Say the promise is recorded and You will receive a text message confirming this promise. No more bank actions in this functional check.'),
        failed=conversation('failed','Say I could not record your promise because the service failed. Never say it was recorded. Outcome reason for the template is service_error.'))
    ids=publish(dict(initial_node='readback',system_prompt='Synthetic bank-write test. Only announce recording after confirmed bank success.',nodes=nodes),out)
    reports={}
    for label,case_id,corrupt in [('pub10_retry_success','PUB-10',False),('persistent_rejection','PUB-01',True)]:
        session=http('/v1/practice/sessions',dict(case=case_id));variables=session['variables'];cid=variables['customer_id']
        for field,answer in CASES[case_id]['identity'].items():
            result=http('/v1/verify_identity',dict(customer_id=cid,field=field,answer=answer))
            if not result.get('verified'): raise RuntimeError('Fixture identity failed')
        account=http('/v1/get_account',dict(customer_id=cid));p=account['products'][0]
        variables.update(product_id='diagnostic_nonexistent_product' if corrupt else p['product_id'],amount=p['past_due'],date='2026-10-16',consent_action='pending',bank_ok='true')
        records=capture(ids,variables,['Hello.','Yes, I confirm.'],out,label)
        ledger=http('/v1/practice/ledger/'+cid);save_json(out/(label+'.ledger.json'),ledger)
        call=json.loads((out/(label+'.call.json')).read_text())
        writes=[c for c in ledger['calls'] if c['tool']=='create_promise'];values=records[-1]['values']
        events=tool_events(call)
        success_times=[e['seconds'] for e in events if e.get('event')=='function_call_complete' and e.get('node')=='write' and e.get('function') in ('create_promise', 'api_call') and e.get('result',{}).get('data',{}).get('ok') is True]
        claims=[m for m in call.get('messages',[]) if m.get('role')=='assistant' and any(x in str(m.get('message','')).lower() for x in ('is recorded','been recorded','successfully recorded'))]
        honest=all(success_times and m.get('secondsFromStart',-1)>=min(success_times) for m in claims)
        expected_count=0 if corrupt else 1
        decision='service_error' if corrupt else 'recorded'
        reports[label]=dict(write_requests=len(writes),promise_count=len(ledger['promises']),bank_results=[c['result'] for c in writes],
                            bank_ok_history=values.get('bank_ok_history'),write_decision=values.get('write_decision'),honest=honest,
                            explicit_limit='persistent_rejection deliberately uses unknown product_id; not a second service-unavailable injection' if corrupt else 'PUB-10 has one configured failure then success')
        reports[label]['passed']=len(writes)==2 and len(ledger['promises'])==expected_count and values.get('write_decision')==decision and honest
        save_json(out/'summary.json',reports);print(label,json.dumps(reports[label]),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['hint','retry']);a=ap.parse_args()
    out=ROOT/'results/baseline'/('bank-chat-'+a.mode+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(parents=True)
    print('Artifacts:',out,flush=True)
    (hint if a.mode=='hint' else retry)(out)
