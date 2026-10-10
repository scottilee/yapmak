"""Budget, provenance, extraction permissions, and publish recovery without external writes."""
import asyncio
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
from types import SimpleNamespace
import pytest
import build
import extract
import freya
import runcontrol
from trace import Trace

ROOT = Path(__file__).resolve().parents[1]


def test_file_allowlist_blocks_escape_symlink_and_source_writes(tmp_path):
    source = tmp_path / 'brief.md'
    source.write_text('brief')
    output = tmp_path / 'policy.json'
    external = tmp_path.parent / 'private'
    external.write_text('private')
    (tmp_path / 'link').symlink_to(external)
    guard = extract.file_guard(tmp_path, [source, output], [output])
    def allowed(tool, path):
        result = asyncio.run(guard({'tool_name': tool, 'tool_input': {'file_path': str(path), 'content': '{}'}}, None, {}))
        return result['hookSpecificOutput']['permissionDecision'] == 'allow'
    assert allowed('Read', source)
    assert allowed('Write', output)
    assert not allowed('Write', source)
    assert not allowed('Read', '../private')
    assert not allowed('Read', tmp_path / 'link')
    assert not allowed('Bash', output)
    assert not allowed('Read', ROOT / '.env')


def test_artifact_credentials_rejected(monkeypatch):
    monkeypatch.setenv('FREYA_API_KEY', 'test-secret-value')
    with pytest.raises(ValueError, match='credential'):
        extract.check_artifact('{"phrase":"test-secret-value"}')


def test_extraction_cannot_reuse_old_audit(tmp_path, monkeypatch):
    (tmp_path / 'policy.py').write_text((ROOT / 'policy.py').read_text())
    (tmp_path / 'out').mkdir()
    (tmp_path / 'out/test.audit.json').write_text('{"fixed":["old"]}')
    monkeypatch.setattr(extract, 'ROOT', tmp_path)
    seen = []
    async def query(prompt, purpose, trace, **kwargs):
        cwd = kwargs['cwd']
        seen.append(cwd)
        assert cwd != ROOT and not (cwd / '.env').exists()
        if purpose == 'policy_extraction':
            (cwd / 'out/test.policy.json').write_text((ROOT / 'tests/fixtures/brief_a.policy.json').read_text())
        return {}
    monkeypatch.setattr(extract, '_query', query)
    with pytest.raises(RuntimeError, match='no audit file'):
        extract.extract([str(ROOT / 'briefs/brief-a.md')], str(ROOT / 'tools/openapi.json'), 'test')
    assert len(seen) == 2
    assert not seen[0].exists()  # scratch cleanup


def test_deadline_caps_subprocess_and_sleep():
    start = time.monotonic()
    with pytest.raises(runcontrol.DeadlineExceeded):
        with runcontrol.deadline(0.08):
            runcontrol.run([sys.executable, '-c', 'import time; time.sleep(10)'], seconds=10)
    assert time.monotonic() - start < 2
    with pytest.raises(runcontrol.DeadlineExceeded):
        with runcontrol.deadline(0.03):
            runcontrol.sleep(10)


def test_child_http_calls_share_trace(tmp_path):
    tr = Trace(tmp_path / 'trace.jsonl')
    try:
        subprocess.run([sys.executable, '-c', '''import io, freya
freya.urllib.request.urlopen = lambda *args, **kwargs: io.BytesIO(b'{}')
freya.api('POST', '/test', {})
'''], cwd=ROOT, check=True)
        events = [json.loads(line) for line in tr.path.read_text().splitlines()]
        assert [e['event'] for e in events] == ['freya_call_start', 'freya_call']
        assert all(e['run_id'] == tr.run_id and e['pid'] != os.getpid() for e in events)
        assert events[0]['request_id'] == events[1]['request_id']
    finally:
        tr.close()


def test_ambiguous_create_reconciles_without_second_post(tmp_path, monkeypatch):
    created = []
    def create(name, workflow):
        created.append(name)
        raise urllib.error.URLError('response lost')
    monkeypatch.setattr(freya, 'create_workflow', create)
    monkeypatch.setattr(freya, 'workspace_id', lambda: 'workspace')
    monkeypatch.setattr(freya, 'api', lambda *args, **kwargs: {'workflows': [{'name': created[0], 'id': 'w', 'agentId': 'a'}], 'total': 1})
    monkeypatch.setattr(freya, 'update_workflow', lambda *args: 2)
    state = tmp_path / 'state.json'
    with pytest.raises(urllib.error.URLError):
        freya.save_workflow('test', {}, state)
    result = freya.save_workflow('test', {}, state)
    assert result == {'workflow_id': 'w', 'agent_id': 'a', 'version': 2}
    assert len(created) == 1
    assert json.loads(state.read_text())['test'] == result


def test_invisible_pending_create_never_repeats_post(tmp_path, monkeypatch):
    state = tmp_path / 'state.json'
    state.write_text('{"test":{"pending_name":"test-unique"}}')
    monkeypatch.setattr(freya, 'find_workflow', lambda name: None)
    monkeypatch.setattr(freya, 'create_workflow', lambda *args: pytest.fail('duplicate POST'))
    with pytest.raises(RuntimeError, match='refusing a duplicate'):
        freya.save_workflow('test', {}, state)


@pytest.mark.parametrize('lost_at', ['put', 'publish'])
def test_update_retry_does_not_repeat_successful_write(monkeypatch, lost_at):
    stored = {'nodes': {}, 'agent_config': {'llmConfig': freya.AGENT_LLM}}
    candidate = {'nodes': {'new': {}}}
    calls = []
    version = dict(id='v2', versionNumber=2, isPublished=False)
    def api(method, path, body=None, **params):
        calls.append((method, path))
        if method == 'GET' and path.startswith('/api/v2/workflow/'):
            return {'workflow': {'workflow': copy.deepcopy(stored)}}
        if method == 'GET':
            return {'versions': [dict(version)]}
        if method == 'PUT':
            stored.clear(); stored.update(copy.deepcopy(body['workflow']))
            if lost_at == 'put':
                raise urllib.error.URLError('PUT response lost')
        if method == 'POST':
            version['isPublished'] = True
            if lost_at == 'publish':
                raise urllib.error.URLError('publish response lost')
        return {}
    monkeypatch.setattr(freya, 'api', api)
    monkeypatch.setattr(freya, 'workspace_id', lambda: 'ws')
    with pytest.raises(urllib.error.URLError):
        freya.update_workflow('w', candidate)
    assert freya.update_workflow('w', candidate) == 2
    assert sum(method == 'PUT' for method, _ in calls) == 1
    assert sum(method == 'POST' for method, _ in calls) == 1


def test_failed_simulation_does_not_report_old_chat_or_simulation_results(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results/test.selftest.json').write_text('{"passed":99,"total":99}')
    monkeypatch.setattr(freya, 'validate_workflow', lambda *args: {})
    monkeypatch.setattr(freya, 'save_workflow', lambda *args: dict(workflow_id='w', agent_id='a', version=1))
    monkeypatch.setattr(freya, 'export_workflow', lambda wid, path: Path(path).write_text('{}'))
    monkeypatch.setattr(runcontrol, 'run', lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 2, '', 'failed'))
    args = SimpleNamespace(deadline=1800, briefs=None, policy=str(ROOT / 'tests/fixtures/brief_a.policy.json'),
                           openapi=str(ROOT / 'tools/openapi.json'), slot='test', cases='cases.json', brief=None, no_smoke=True)
    with runcontrol.deadline(1800):
        build.build(args)
    records = [json.loads(line) for line in (tmp_path / 'traces/test.jsonl').read_text().splitlines()]
    event = next(r for r in records if r['event'] == 'simulation')
    assert event['exit_code'] == 2 and event['passed'] is None and not event['result_valid']
    assert '.simulation.json' in event['result_path']


def test_sdk_records_each_response_and_tool_call_even_when_session_fails(tmp_path, monkeypatch):
    import claude_agent_sdk as sdk
    async def query(*, prompt, options):
        assert options.tools == ['Read', 'Write']
        assert options.hooks['PreToolUse']
        yield sdk.AssistantMessage(content=[sdk.ToolUseBlock(id='tool-1', name='Read', input={'file_path': 'brief.md'})], model='test', message_id='request-1')
        yield sdk.AssistantMessage(content=[sdk.TextBlock(text='done')], model='test', message_id='request-2')
        raise RuntimeError('provider disconnected')
    monkeypatch.setattr(sdk, 'query', query)
    tr = Trace(tmp_path / 'trace.jsonl')
    try:
        with pytest.raises(RuntimeError, match='provider disconnected'):
            asyncio.run(extract._query('test', 'test', tr, cwd=tmp_path, readable=[], writable=[]))
        records = [json.loads(line) for line in tr.path.read_text().splitlines()]
        assert [r['request_id'] for r in records if r['event'] == 'model_response'] == ['request-1', 'request-2']
        assert len([r for r in records if r['event'] == 'model_tool_call']) == 1
        assert records[-1]['event'] == 'model_session_end' and 'disconnected' in records[-1]['error']
    finally:
        tr.close()


def test_saved_workflow_comparison_detects_deleted_nodes():
    assert not freya._contains({'nodes': {'keep': {}, 'remove': {}}}, {'nodes': {'keep': {}}})
    assert freya._contains({'nodes': {'keep': {'platform_default': True}}}, {'nodes': {'keep': {}}})


def test_registry_atomic_replace_preserves_old_file_on_failure(tmp_path, monkeypatch):
    path = tmp_path / 'registry.json'
    path.write_text('{"previous": true}')
    def fail(*args):
        raise OSError('disk failure')
    monkeypatch.setattr(freya.os, 'replace', fail)
    with pytest.raises(OSError):
        freya.atomic_json(path, {'new': True})
    assert json.loads(path.read_text()) == {'previous': True}
    assert list(tmp_path.iterdir()) == [path]


def test_expired_budget_does_not_start_a_child(monkeypatch):
    monkeypatch.setenv(runcontrol.DEADLINE_ENV, str(time.monotonic() - 1))
    monkeypatch.setattr(runcontrol.subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('child started after deadline'))
    with pytest.raises(runcontrol.DeadlineExceeded):
        runcontrol.run([sys.executable, '-c', 'pass'], seconds=10)
