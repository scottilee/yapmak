"""Shared chat lifecycle, trace security and visible runtime failures."""
import ast
import io
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error
import pytest
import freya
import compile as C
import policy as P
import trace
from artifact_security import check_artifact
from retrying import retry
from scripts.chatlib import Chat, variables_from, runtime_errors
from scripts.chat_selftest import evidence_checks, scenario_identity

ROOT = Path(__file__).resolve().parents[1]


def transcript():
    return {'messages': [
        {'message': 'hello'},
        {'message': json.dumps({'event': 'node_enter', 'variable_table': {'runtime_error': {'value': 'bad deadline'}, 'flag': {'value': False}}}), 'nodeId': 'setup'},
        {'workflowSnapshot': {'variableTable': {'count': {'value': 0}}}, 'message': 'not json'},
        {'message': {'event': 'route_evaluated', 'target': 'ask_0', 'matched': True,
                     'variable_table': {'runtime_error': {'value': ''}, 'holder': 'confirmed'}}},
    ]}


def test_parser_uses_real_events_and_preserves_falsy_values():
    values, events = variables_from(transcript())
    assert values == dict(runtime_error='', flag=False, count=0, holder='confirmed')
    assert [e['event'] for e in events] == ['node_enter', 'route_evaluated']
    assert events[0]['node'] == 'setup'
    assert runtime_errors(transcript()) == ['bad deadline']


def test_selftest_reports_earlier_runtime_error_even_when_later_cleared():
    checks = evidence_checks(SimpleNamespace(evidence=transcript), 'ask_0')
    assert next(c for c in checks if c['name'] == 'no_runtime_error')['pass'] is False
    assert next(c for c in checks if c['name'] == 'routed_to_ask_0')['pass'] is True


def test_missing_evidence_is_not_claimed_clean():
    checks = evidence_checks(SimpleNamespace(evidence=lambda: {'messages': []}), 'ask_0')
    assert checks[0]['pass'] is None and checks[0]['soft'] is True


def test_chat_cleans_up_on_failed_turn_without_replaying(monkeypatch):
    calls = []
    def api(method, path, body):
        calls.append((path, body))
        if path.endswith('/end'):
            return {}
        if body['message'] == 'Hello':
            return {'callId': 'call', 'response': 'Hi'}
        raise urllib.error.URLError('response lost')
    monkeypatch.setattr(freya, 'api', api)
    with pytest.raises(urllib.error.URLError):
        with Chat('workflow', {'now': 'today'}) as chat:
            chat.send('Hello')
            chat.send('Yes')
    assert len(calls) == 3
    assert calls[-1] == ('/api/v2/chat/end', {'callId': 'call'})
    assert calls[1][1] == {'message': 'Yes', 'callId': 'call'}


def test_identity_scenario_cleans_up_on_second_turn_failure(monkeypatch):
    calls = []
    def api(method, path, body):
        calls.append(path)
        if path.endswith('/end'):
            return {}
        if body['message'] == 'Hello?':
            return {'callId': 'call', 'response': 'Hello?'}
        raise RuntimeError('second turn failed')
    monkeypatch.setattr(freya, 'api', api)
    ir = P.PolicyIR.load(str(ROOT / 'tests/fixtures/brief_a.policy.json'))
    with pytest.raises(RuntimeError, match='second turn'):
        scenario_identity('wf', ir, {})
    assert calls[-1] == '/api/v2/chat/end'


def test_dynamic_trace_redaction_and_artifact_gate(monkeypatch):
    monkeypatch.setenv('FREYA_API_KEY', 'secret-added-after-import')
    value = 'secret-added-after-import fak_1234567890123456 sk-ant-1234567890123456 Authorization: Bearer abcdefghijklmnop'
    redacted = trace._scrub({'error': (value,)})['error'][0]
    assert 'secret-added-after-import' not in redacted
    assert '1234567890123456' not in redacted and 'abcdefghijklmnop' not in redacted
    with pytest.raises(ValueError, match='credential'):
        check_artifact(value)
    check_artifact(redacted)


def test_http_error_body_redacted_before_exception(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://example.test', 503, 'Unavailable', {}, io.BytesIO(b'fak_1234567890123456'))
    monkeypatch.setattr(freya.urllib.request, 'urlopen', fail)
    with pytest.raises(freya.APIError) as exc:
        freya.api('GET', '/test')
    assert 'fak_' not in str(exc.value) and '[REDACTED]' in str(exc.value)


def test_secret_workflow_rejected_before_network_call(monkeypatch):
    monkeypatch.setattr(freya, 'api', lambda *a, **k: pytest.fail('network call with secret'))
    with pytest.raises(ValueError, match='credential'):
        freya.validate_workflow('test', {'system_prompt': 'fak_1234567890123456'})


def test_shared_retry_only_retries_transient_errors(monkeypatch):
    import retrying
    sleeps, calls = [], []
    monkeypatch.setattr(retrying.runcontrol, 'sleep', sleeps.append)
    def transient():
        calls.append(1)
        if len(calls) < 2:
            raise freya.APIError('GET', '/test', 503, 'unavailable')
        return 'ok'
    assert retry(transient, 'read', attempts=2, wait_s=1) == 'ok'
    assert sleeps == [1]
    def permanent():
        raise freya.APIError('GET', '/test', 401, 'unauthorized')
    with pytest.raises(freya.APIError):
        retry(permanent, 'read', attempts=3)
    assert sleeps == [1]


def test_emitted_runtime_excludes_legacy_calendar_helpers():
    ir = P.PolicyIR.load(str(ROOT / 'tests/fixtures/brief_a.policy.json'))
    wf = C.compile_workflow(ir, C.parse_openapi(str(ROOT / 'tools/openapi.json')))
    for node in wf['nodes'].values():
        for action in node.get('pre_actions', []):
            fn = action['function']
            if fn['handler'] == '__function__:code_exec':
                tree = ast.parse(fn['parameters']['properties']['code']['default'])
                names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
                assert not names.intersection({'parse_amount', 'resolve_date_expression', 'callback_slot'})
    assert len(C.embed_policy(ir)) < len(json.dumps(json.loads(C.embed_policy(ir)), indent=1))


@pytest.mark.parametrize('url', ['https://bad host.example/v1', 'https://bad_host.example/v1', 'https://example.test:bad/v1'])
def test_invalid_server_host_rejected(tmp_path, url):
    spec = json.loads((ROOT / 'tools/openapi.json').read_text())
    spec['servers'][0]['url'] = url
    path = tmp_path / 'api.json'; path.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        C.parse_openapi(str(path))


def test_cross_origin_bank_operation_rejected(tmp_path):
    spec = json.loads((ROOT / 'tools/openapi.json').read_text())
    spec['paths']['/create_promise']['post']['servers'] = [{'url': 'https://other.example/v1'}]
    path = tmp_path / 'api.json'; path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='same HTTPS origin'):
        C.parse_openapi(str(path))


def test_event_metadata_can_already_contain_node_and_seconds():
    from scripts.chatlib import events
    call = {'messages': [{'nodeId': 'outer', 'secondsFromStart': 1,
                          'message': {'event': 'node_enter', 'node': 'inner', 'seconds': 2}}]}
    parsed = list(events(call))[0]
    assert parsed['node'] == 'inner' and parsed['seconds'] == 2
