"""Validate, publish, read back and smoke-test a compiled workflow on Freya.

    source .env; .venv/bin/python scripts/publish_check.py <slot> out/<file>.workflow.json [--no-chat]

Steps: dry-run -> save_workflow (publishes) -> GET and diff against the candidate (the platform strips fields silently)
-> export checkpoint -> one chat turn to see the opening line. Never starts a simulation.
"""
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402
from scripts.chatlib import Chat, variables_from, runtime_errors

from compiler_checks import workflow_diff


def main():
    slot, path = sys.argv[1], sys.argv[2]
    wf = json.load(open(path))
    t0 = time.time()
    freya.validate_workflow(slot, wf)
    print(f"dry-run ok ({time.time() - t0:.1f}s)")
    t0 = time.time()
    ids = freya.save_workflow(slot, wf)
    print("published", ids, f"({time.time() - t0:.1f}s)")
    stored = freya.api("GET", f"/api/v2/workflow/{ids['workflow_id']}", workspaceId=freya.workspace_id())["workflow"]["workflow"]
    d = workflow_diff(wf, stored)
    print("stored-vs-candidate differences:", len(d))
    for line in d[:40]:
        print("  ", line)
    (ROOT / "out").mkdir(exist_ok=True)
    freya.export_workflow(ids["workflow_id"], str(ROOT / "out" / f"{slot}.export.json"))
    print("checkpoint exported to", f"out/{slot}.export.json")
    if "--no-chat" in sys.argv:
        return
    cv = {"customer_id": "c_smoke", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}
    with Chat(ids["workflow_id"], cv) as session:
        for msg in ["Hello?", "Yes, speaking."]:
            t0 = time.time()
            response = session.send(msg)
            print(f"chat> {msg}\nagent< {response.get('response')!r} ({time.time() - t0:.1f}s)")
        call = session.evidence()
        values, events = variables_from(call)
        for event in events:
            if event['event'] in ('route_evaluated', 'error', 'function_call_complete'):
                print("  event:", event['event'], event.get('from_node') or event.get('function') or '', '->', event.get('target', ''))
        for key in ('next', 'runtime_error', 'today_text', 'id_say', 'state_json'):
            if key in values:
                print(f"  var {key} = {str(values[key])[:160]}")
        errors = runtime_errors(call)
        if errors:
            raise RuntimeError("workflow runtime errors: " + "; ".join(errors))


if __name__ == "__main__":
    main()
