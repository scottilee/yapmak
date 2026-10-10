"""Shared chat lifecycle and transcript decoding; never starts a simulation.

Chat POSTs are not retried automatically: a lost response may still have advanced
or written through the workflow. Read-only evidence fetches use the shared retry.
"""
import json
import freya
from retrying import retry
from trace import inherited_event


def events(call):
    """Decode structured events and preserve their transcript metadata."""
    for message in (call or {}).get('messages', []):
        raw = message.get('message', '')
        try:
            event = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(event, dict) and event.get('event'):
            yield {'seconds': message.get('secondsFromStart'), 'node': message.get('nodeId'), **event}


def _values(table):
    return {k: v.get('value') if isinstance(v, dict) and 'value' in v else v for k, v in table.items()}


def variables_from(call):
    """Merge snapshots in transcript order; expose current raw values, including false/zero.

    Known route events are route_evaluated, node_enter and node_exit. Preserve
    all events for consumers instead of relying on speculative event names.
    """
    values = {}
    for message in (call or {}).get('messages', []):
        snapshot = message.get('workflowSnapshot') or {}
        table = snapshot.get('variableTable')
        if isinstance(table, dict):
            values.update(_values(table))
        raw = message.get('message', '')
        try:
            event = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(event, dict) and isinstance(event.get('variable_table'), dict):
            values.update(_values(event['variable_table']))
    return values, list(events(call))


def runtime_errors(call):
    """Retain earlier errors even if a later snapshot clears runtime_error."""
    errors = []
    for message in (call or {}).get('messages', []):
        value = variables_from({'messages': [message]})[0].get('runtime_error')
        if value and str(value) not in errors:
            errors.append(str(value))
    return errors


class Chat:
    def __init__(self, workflow_id, variables=None, on_cleanup_error=None):
        self.workflow_id = workflow_id
        self.variables = variables or {}
        self.call_id = None
        self.on_cleanup_error = on_cleanup_error

    def __enter__(self):
        return self

    def send(self, message):
        body = {'message': message}
        if self.call_id:
            body['callId'] = self.call_id
        else:
            body.update(workflowId=self.workflow_id, customerVariables=self.variables)
        result = freya.api('POST', '/api/v2/chat/message', body)
        self.call_id = result.get('callId') or self.call_id
        if not self.call_id:
            raise RuntimeError('chat response did not contain a callId')
        return result

    def evidence(self):
        if not self.call_id:
            raise RuntimeError('chat has not started')
        return retry(lambda: freya.get_call(self.call_id), 'chat_evidence', attempts=2, wait_s=2)

    def __exit__(self, exc_type, exc, tb):
        if self.call_id:
            try:
                freya.api('POST', '/api/v2/chat/end', {'callId': self.call_id})
            except Exception as error:
                inherited_event('chat_cleanup_error', call_id=self.call_id, error=repr(error))
                if self.on_cleanup_error:
                    self.on_cleanup_error(error)
        return False
