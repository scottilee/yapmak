"""Regression tests for review findings at the policy/compiler boundary."""
import copy
import json
from pathlib import Path
import pytest
import compile as C
import policy as P

ROOT = Path(__file__).resolve().parents[1]


def policy():
    return P.PolicyIR.load(str(ROOT / 'tests/fixtures/brief_a.policy.json'))


def tools():
    return C.parse_openapi(str(ROOT / 'tools/openapi.json'))


@pytest.mark.parametrize('change', [
    lambda p: p.bands[0].deadline.update(n=-3),
    lambda p: p.bands[0].deadline.update(n=True),
    lambda p: p.bands[0].deadline.update(kind='fixed_date', date='2026-02-30', adjustment='none'),
    lambda p: p.calendar.holidays.append('2026-99-99'),
    lambda p: setattr(p.calendar, 'business_days', []),
    lambda p: setattr(p.outcomes, 'promise_outcome', 'not_an_api_outcome'),
    lambda p: setattr(p.identity, 'failed_outcome', ('not_an_api_outcome', '')),
    lambda p: setattr(p.outcomes, 'service_error_reason', 'not_an_api_reason'),
    lambda p: p.bands.append(copy.deepcopy(p.bands[0])),
])
def test_invalid_policy_is_rejected(change):
    ir = policy()
    change(ir)
    assert P.validate(ir, C.tool_enums(tools()))


def test_callback_dates_do_not_require_payment_offer():
    wf = C.compile_workflow(policy(), tools())
    callback = next(e for e in wf['nodes']['third_party']['extraction_schema'] if e['name'] == 'cb_kind')
    payment = next(e for e in wf['nodes']['negotiate']['extraction_schema'] if e['name'] == 'prop_kind')
    assert 'payment' not in callback['description']
    assert 'reaching the customer' in callback['description']
    assert 'Only a day the customer offers as a payment day counts' in payment['description']


def test_all_verified_cannot_skip_policy_questions():
    ir = policy()
    ir.identity.requirements *= 2
    ns = {}
    exec(C.RUNTIME, ns)
    state, routed = {}, []
    values = dict(v_ok='true', v_verified='true', v_all='true', v_left='3')
    ns.update(POLICY=ir.to_dict(), vars={}, _S=lambda: state, _save=lambda s: None,
              _get=lambda k: values.get(k, ''), _clear=lambda *args: None,
              _ask_text=lambda i: str(i), _set_next=routed.append)
    for i in range(4):
        ns['st_verify_after'](i)
    assert routed == ['ask_1', 'ask_2', 'ask_3', 'get_account']


def test_bad_deadline_does_not_become_today():
    ns = {}
    exec(C.RUNTIME, ns)
    state = {'today': '2026-10-14'}
    slots = C.response_slots(tools())
    account = slots['account']
    raw = {account['id']: 'p1', account['type']: 'loan', account['past_due']: 100, account['days_late']: 5}
    ns.update(POLICY=policy().to_dict(), SLOTS=slots, vars={}, _S=lambda: state, _save=lambda s: None,
              _products_from_vars=lambda: [raw], _cal=lambda: ([], [0,1,2,3,4]),
              _name=lambda p: 'loan', _floor_of=lambda p: 10, deadline=lambda *args: None,
              _stuck=lambda stage: False)
    ns['_run']('init_products')
    assert 'Cannot resolve policy deadline' in ns['vars']['runtime_error']
    assert ns['vars']['next'] == 'finalize'
    assert 'products' not in state


def write_api(tmp_path, mutate):
    spec = json.loads((ROOT / 'tools/openapi.json').read_text())
    mutate(spec)
    path = tmp_path / 'api.json'
    path.write_text(json.dumps(spec))
    return path


def test_openapi_refs_201_and_path_metadata(tmp_path):
    original = tools()
    def mutate(spec):
        spec['components'] = {'schemas': {}}
        for n, item in enumerate(spec['paths'].values()):
            item['parameters'] = [{'in': 'query', 'name': 'unused', 'required': False, 'schema': {'type': 'string'}}]
            for method, op in list(item.items()):
                if method == 'parameters':
                    continue
                schema = op['responses']['200']['content']['application/json']['schema']
                spec['components']['schemas'][str(n)] = schema
                op['responses']['201'] = op['responses'].pop('200')
                op['responses']['201']['content']['application/json']['schema'] = {'$ref': '#/components/schemas/' + str(n)}
    mapped = C.parse_openapi(str(write_api(tmp_path, mutate)))
    assert mapped.keys() == original.keys()
    assert C.response_slots(mapped) == C.response_slots(original)
    assert not C.static_check(C.compile_workflow(policy(), mapped), mapped)


@pytest.mark.parametrize('mutation', [
    lambda s: s['servers'][0].update(url='http://bank.example'),
    lambda s: next(iter(s['paths'].values())).update(parameters=[{'in': 'query', 'name': 'token', 'required': True}]),
    lambda s: next(iter(s['paths'].values())).update({'$ref': 'https://example.com/schema'}),
])
def test_unsupported_api_fails_explicitly(tmp_path, mutation):
    with pytest.raises(ValueError):
        C.parse_openapi(str(write_api(tmp_path, mutation)))


def test_policy_roundtrip_retains_dataclasses_and_rejects_wrong_types():
    original = policy()
    restored = P.PolicyIR.from_dict(json.loads(original.to_json()))
    assert restored == original
    assert isinstance(restored.identity.requirements[0], P.IdentityRequirement)
    data = original.to_dict()
    data['identity']['wrong_answer_limit'] = '3'
    with pytest.raises(ValueError, match='wrong_answer_limit'):
        P.PolicyIR.from_dict(data)


def test_compile_api_also_rejects_invalid_outcomes():
    ir = policy()
    ir.outcomes.promise_outcome = 'not_an_api_outcome'
    with pytest.raises(ValueError, match='unknown outcome'):
        C.compile_workflow(ir, tools())


@pytest.fixture(scope='module')
def public_workflows():
    return {
        'A': C.compile_workflow(policy(), tools()),
        'B': C.compile_workflow(P.PolicyIR.load_merged([str(ROOT / 'tests/fixtures/brief_a.policy.json'),
                                                     str(ROOT / 'tests/fixtures/brief_ab.policy.json')]), tools()),
    }


PUBLIC_CASES = json.loads((ROOT / 'public-test-set.json').read_text())
PUBLIC_CASES.append(dict(PUBLIC_CASES[0], id='PUB-01-pieces'))


@pytest.mark.parametrize('case', PUBLIC_CASES, ids=lambda c: c['id'])
def test_public_state_machine_contracts_after_refactor(public_workflows, case):
    import sys
    sys.path.insert(0, str(ROOT / 'tests'))
    from offline_sim import run_case
    bad, bank, driver = run_case(public_workflows[case['brief']], case)
    assert not bad, bad
