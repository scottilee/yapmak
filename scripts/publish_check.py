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

IGNORED_TOP = {"agent_config", "nodePositions", "test_variables", "tools", "context_variables"}


def diff(a, b, path="", out=None):
    out = out if out is not None else []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if path == "" and k in IGNORED_TOP:
                continue
            if k not in b:
                out.append(f"{path}.{k}: missing in stored")
            elif k not in a:
                out.append(f"{path}.{k}: added by platform")
            else:
                diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: list length {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out)
    elif a != b and not (a in ("", None, False) and b in ("", None, False)):
        out.append(f"{path}: {str(a)[:60]!r} -> {str(b)[:60]!r}")
    return out


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
    d = diff(wf, stored)
    print("stored-vs-candidate differences:", len(d))
    for line in d[:40]:
        print("  ", line)
    (ROOT / "out").mkdir(exist_ok=True)
    freya.export_workflow(ids["workflow_id"], str(ROOT / "out" / f"{slot}.export.json"))
    print("checkpoint exported to", f"out/{slot}.export.json")
    if "--no-chat" in sys.argv:
        return
    cv = {"customer_id": "c_smoke", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}
    call_id = None
    try:
        for msg in ["Hello?", "Yes, speaking."]:
            body = {"workflowId": ids["workflow_id"], "message": msg}
            if call_id:
                body["callId"] = call_id
            else:
                body["customerVariables"] = cv
            t0 = time.time()
            r = freya.api("POST", "/api/v2/chat/message", body)
            call_id = r.get("callId", call_id)
            print(f"chat> {msg}\nagent< {r.get('response')!r} ({time.time() - t0:.1f}s)")
        call = freya.get_call(call_id)
        snap = {}
        for m in call.get("messages", []):
            try:
                ev = json.loads(m.get("message", ""))
                if isinstance(ev, dict) and ev.get("event") in ("route_evaluated", "error", "function_call_complete"):
                    print("  event:", ev.get("event"), ev.get("from_node") or ev.get("function") or "", "->", ev.get("target", ""), str(ev.get("message", ""))[:200])
                    snap = ev.get("variable_table") or snap
            except (ValueError, TypeError):
                pass
        for k in ("next", "runtime_error", "today_text", "id_say", "state_json"):
            if k in snap:
                v = snap[k]
                print(f"  var {k} = {str(v.get('value') if isinstance(v, dict) else v)[:160]}")
    finally:
        if call_id:
            freya.api("POST", "/api/v2/chat/end", {"callId": call_id})


if __name__ == "__main__":
    main()
