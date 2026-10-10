"""Small chat-only functional checks. Reuses runtime-check; never starts simulations."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import freya
from scripts.chatlib import Chat, variables_from
from trace import _scrub
from score import http


def route(target, variable=None, operand=None):
    condition = {'operator': 'always'} if variable is None else {'variable': variable, 'operator': 'is_set' if operand is None else 'equals'}
    if operand is not None:
        condition['operand'] = operand
    return {'target_node': target, 'description': 'Deterministic ' + target, 'condition': condition}


def conversation(name, prompt, extraction=None, transitions=None):
    return dict(name=name, node_type='conversation', task_message=prompt, on_enter={'type': 'llm'},
                extraction_schema=extraction or [], transitions=transitions or [], tools=[], max_node_turns=12)


def code_node(source, transitions):
    return dict(name='check', node_type='code', passthrough=True, on_enter={'type': 'silent'},
                passthrough_default_transition=transitions[-1]['target_node'], transitions=transitions,
                pre_actions=[{'type': 'function', 'function': {'name': 'code_exec', 'handler': '__function__:code_exec',
                'parameters': {'type': 'object', 'properties': {'code': {'type': 'string', 'default': source}, 'timeout_ms': {'type': 'number', 'default': 10000}}}}}])


def save_json(path, value):
    path.write_text(json.dumps(_scrub(value), indent=2))


def publish(workflow, out):
    save_json(out / 'candidate.json', workflow)
    freya.validate_workflow('runtime-check', workflow)
    ids = freya.save_workflow('runtime-check', workflow)
    # First create may need the client's model-pinning/publish path.
    if 'version' not in ids:
        ids['version'] = freya.update_workflow(ids['workflow_id'], workflow)
    freya.export_workflow(ids['workflow_id'], str(out / 'export.json'))
    save_json(out / 'ids.json', ids)
    return ids


def chat(ids, variables, messages, out, label):
    turns = []
    def cleanup(error):
        save_json(out / (label + '.end-error.json'), {'error': str(error)})
    with Chat(ids['workflow_id'], variables, on_cleanup_error=cleanup) as session:
        for message in messages:
            result = session.send(message)
            turns.append({'input': message, 'result': result})
            save_json(out / (label + '.turns.json'), turns)
        call = session.evidence()
        save_json(out / (label + '.call.json'), call)
        return call


def date_check(out):
    schema = [{'name': 'wanted_date', 'type': 'date', 'description': 'The date the caller requests.', 'min_confidence': 0.0}]
    nodes = {'collect': conversation('collect', 'Ask which date the caller requests. Do not infer a date yourself.', schema, [route('check', 'wanted_date')]),
             'check': code_node("vars['observed_now'] = str(vars.get('now', 'missing'))\nvars['code_ran'] = 'yes'\nvars['code_date'] = str(vars.get('now', ''))[:10]\n", [route('observe')]),
             'observe': conversation('observe', 'State the extracted date {{wanted_date}} and say the check is complete. Do not change the date.')}
    ids = publish(dict(initial_node='collect', system_prompt='You are a calendar test assistant. Speak English.', nodes=nodes), out)
    report = {}
    for label, expression in [('friday', 'next Friday'), ('tomorrow', 'tomorrow')]:
        call = chat(ids, {'now': '2026-10-14T11:00'}, ['Hello.', 'I would like ' + expression + '.'], out, label)
        values, _ = variables_from(call)
        report[label] = {k: values.get(k) for k in ('wanted_date', 'observed_now', 'code_ran', 'code_date', 'system.iso_utc_now')}
        report[label]['call_id'] = call.get('id') or call.get('callId')
    save_json(out / 'summary.json', report)
    print(json.dumps(report, indent=2), flush=True)


def guard_check(out):
    source = """vars['verdict'] = 'blocked'
vars['run_check'] = ''
try:
    amount = float(vars.get('proposal_amount', 0))
    floor = float(vars.get('floor', 0))
    full = float(vars.get('full', 0))
    confirmed = str(vars.get('confirmed', '')).lower() == 'true'
    attempted = str(vars.get('attempted', '')).lower() == 'true'
    if floor <= amount <= full and confirmed and not attempted:
        vars['verdict'] = 'ok'
        vars['attempted'] = 'true'
except Exception:
    vars['verdict'] = 'blocked'
"""
    spec = json.loads((ROOT / 'tools/openapi.json').read_text())
    schema = spec['paths']['/create_promise']['post']['requestBody']['content']['application/json']['schema']
    body = json.loads(json.dumps(schema))
    for key, value in body['properties'].items():
        value['default'] = '{{' + ('proposal_amount' if key == 'amount' else key) + '}}'
    tool = {'type': 'function', 'config': {'maxRetries': 0, 'timeoutMs': 10000}, 'function': {
        'name': 'create_promise', 'handler': '__function__:api_call', 'parameters': {'type': 'object', 'properties': {
            'url': {'type': 'string', 'default': spec['servers'][0]['url'] + '/create_promise'},
            'method': {'type': 'string', 'default': 'POST'},
            'headers': {'type': 'object', 'properties': {'Content-Type': {'type': 'string', 'default': 'application/json'}}},
            'body': body}}}}
    extraction = [{'name': 'run_check', 'type': 'string', 'enum_values': ['check'], 'description': 'Set check when the caller asks to check the proposal or check again.', 'min_confidence': 0.0}]
    collect = conversation('collect', 'If asked to check, explain that only valid confirmed proposals can be recorded. Otherwise ask the caller to say check the proposal.', extraction, [route('check', 'run_check', 'check')])
    recorded = conversation('recorded', 'The bank returned success. Say the promise is recorded. If asked to check again, run the check.', extraction, [route('check', 'run_check', 'check')])
    success = {'logic': 'or', 'conditions': [{'variable': 'bank_ok', 'operator': 'equals', 'operand': v} for v in ('true', 'True')]}
    write = dict(name='write', node_type='api_request', passthrough=True, on_enter={'type': 'silent'}, passthrough_default_transition='collect',
                 pre_actions=[tool], response_mapping=[{'path': 'data.ok', 'variable': 'bank_ok'}],
                 transitions=[{'target_node': 'recorded', 'description': 'Bank data.ok is true', 'condition': success}, route('collect')])
    nodes = dict(collect=collect, check=code_node(source, [route('write', 'verdict', 'ok'), route('collect')]), write=write, recorded=recorded)
    ids = publish(dict(initial_node='collect', system_prompt='You are a functional test assistant. Speak English. Do not claim recording unless bank success is reported.', nodes=nodes), out)
    case = next(c for c in json.loads((ROOT / 'public-test-set.json').read_text()) if c['id'] == 'PUB-01')
    report = {}
    for label, consent, valid in [('invalid', True, False), ('unconfirmed', False, True), ('confirmed', True, True)]:
        session = http('/v1/practice/sessions', {'case': case['id']})
        variables = session['variables']
        cid = variables['customer_id']
        for field, answer in case['identity'].items():
            result = http('/v1/verify_identity', {'customer_id': cid, 'field': field, 'answer': answer})
            if not result.get('ok') or not result.get('verified'):
                raise RuntimeError('Fixture identity setup failed')
        account = http('/v1/get_account', {'customer_id': cid})
        product = account['products'][0]
        floor = product.get('minimum_payment', product.get('instalment_amount'))
        variables.update(product_id=product['product_id'], proposal_amount=product['past_due'] if valid else floor - 1,
                         floor=floor, full=product['past_due'], date=variables['now'][:10], confirmed='true' if consent else 'false', attempted='false')
        before = http('/v1/practice/ledger/' + cid)
        call = chat(ids, variables, ['Hello.', 'Check the proposal.', 'Check again.'], out, label)
        ledger = http('/v1/practice/ledger/' + cid)
        save_json(out / (label + '.ledger.json'), ledger)
        values, events = variables_from(call)
        writes = [c for c in ledger['calls'] if c['tool'] == 'create_promise']
        report[label] = dict(promise_count=len(ledger['promises']), write_requests=len(writes), before_promises=len(before['promises']),
                             verdict=values.get('verdict'), bank_ok=values.get('bank_ok'), attempted=values.get('attempted'),
                             transitions=[dict(from_node=e.get('from_node'), to_node=e.get('target', e.get('to_node')), matched=e.get('matched'), reason=e.get('reason')) for e in events if e.get('matched')])
        expected = 1 if consent and valid else 0
        report[label]['passed'] = len(writes) == expected and len(ledger['promises']) == expected and (expected == 0 or str(values.get('bank_ok')).lower() == 'true')
        save_json(out / 'summary.json', report)
        if not report[label]['passed']:
            raise RuntimeError('Guard acceptance failed for ' + label)
        print(label, json.dumps(report[label]), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('check', choices=['date', 'guard']); a = ap.parse_args()
    out = ROOT / 'results/baseline' / ('runtime-' + a.check + '-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir(parents=True)
    print('Artifacts:', out, flush=True)
    (date_check if a.check == 'date' else guard_check)(out)
