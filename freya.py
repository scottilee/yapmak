"""Thin client for the Freya API. Standard library only.

    export FREYA_API_KEY=fak_...            # your workspace key
    export FREYA_API_URL=https://staging-app.freyavoice.ai   # default
"""
import json, os, time, urllib.request, urllib.error, urllib.parse
import pathlib
import tempfile
import uuid
import fcntl
import runcontrol
from trace import inherited_event
from artifact_security import check_artifact, redact

URL = os.environ.get("FREYA_API_URL", "https://staging-app.freyavoice.ai")
# Cloudflare rejects requests without a browser-like User-Agent (error 1010).
HEADERS = {"Authorization": "Bearer " + os.environ.get("FREYA_API_KEY", ""), "Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (build-the-builder)"}

class APIError(RuntimeError):
    def __init__(self, method, path, status, detail):
        self.status = status
        super().__init__(f"{method} {path} -> {status}: {detail}")


def api(method, path, body=None, **params):
    """Shared tracing covers parent and child processes, including interrupted requests."""
    q = "?" + urllib.parse.urlencode(params) if params else ""
    request_id = uuid.uuid4().hex
    started = time.monotonic()
    inherited_event("freya_call_start", request_id=request_id, method=method, path=path)
    try:
        req = urllib.request.Request(URL + path + q, data=json.dumps(body).encode() if body is not None else None, headers=HEADERS, method=method)
        try:
            with urllib.request.urlopen(req, timeout=runcontrol.timeout(120)) as r:
                out = json.load(r)
        except urllib.error.HTTPError as e:
            raise APIError(method, path, e.code, redact(e.read().decode(errors="replace"))[:1500]) from None
        if isinstance(out, dict) and out.get("success") is False:
            raise APIError(method, path, 200, "API reported success=false")
        result = out.get("data", {}).get("result", out) if isinstance(out, dict) else out
    except BaseException as e:
        inherited_event("freya_call", request_id=request_id, method=method, path=path, ok=False,
                        error=repr(e)[:300], duration_ms=int((time.monotonic() - started) * 1000))
        raise
    inherited_event("freya_call", request_id=request_id, method=method, path=path, ok=True,
                    duration_ms=int((time.monotonic() - started) * 1000))
    return result

_ws = None
def workspace_id():
    """The workspace your key belongs to. List routes need it as a query parameter."""
    global _ws
    if not _ws:
        r = api("GET", "/api/v2/workspaces"); items = r.get("workspaces") or r.get("items") or r
        _ws = os.environ.get("FREYA_WORKSPACE_ID") or items[0]["id"]
    return _ws

def create_workflow(name, workflow):
    """Create a workflow. Freya creates its agent with it. Returns {workflow_id, agent_id}."""
    w = api("POST", "/api/v2/workflow", {"name": name, "workflow": workflow})["workflow"]
    return {"workflow_id": w["id"], "agent_id": w["agentId"]}

def atomic_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def find_workflow(name):
    """Reconcile a persisted creation intent by its unique remote name."""
    offset = 0
    matches = []
    while True:
        page = api("GET", "/api/v2/workflow", workspaceId=workspace_id(), limit=100, offset=offset)
        rows = page["workflows"]
        matches.extend(w for w in rows if w.get("name") == name)
        offset += len(rows)
        if not rows or offset >= page["total"]:
            break
    if len(matches) > 1:
        raise RuntimeError("Multiple workflows match a pending creation; reconcile the slot manually")
    if matches:
        w = matches[0]
        return {"workflow_id": w["id"], "agent_id": w["agentId"]}
    return None


def save_workflow(slot, workflow, state_file=None):
    """Serialize local publishers; persist intent before creation and reconcile ambiguous failures.

    Never repeat an ambiguous POST. If the remote workflow is not yet visible, keep the intent
    and fail safely; a later invocation can reconcile it without creating another workflow.
    """
    check_artifact(json.dumps(workflow))
    f = pathlib.Path(state_file) if state_file else pathlib.Path(__file__).resolve().parent / ".freya-agents.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(str(f) + ".lock", "a") as lock:
        wait_until = time.monotonic() + 90
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= wait_until:
                    raise TimeoutError("workflow registry busy for 90 seconds")
                runcontrol.sleep(0.1)
        state = json.loads(f.read_text()) if f.exists() else {}
        entry = state.get(slot)
        if entry and "pending_name" in entry:
            recovered = find_workflow(entry["pending_name"])
            if not recovered:
                raise RuntimeError("Pending workflow creation is not visible; refusing a duplicate POST. "
                                   "Re-run after reconciliation or verify the pending_name in the slot registry.")
            state[slot] = entry = recovered
            atomic_json(f, state)
        if not entry:
            name = f"{slot} {uuid.uuid4().hex}"
            state[slot] = {"pending_name": name}
            atomic_json(f, state)
            try:
                entry = create_workflow(name, workflow)
            except APIError as e:
                # A definitive client rejection did not create a workflow. Timeouts/5xx remain ambiguous.
                if 400 <= e.status < 500 and e.status not in (408, 409):
                    del state[slot]
                    atomic_json(f, state)
                raise
            state[slot] = entry
            atomic_json(f, state)
        entry["version"] = update_workflow(entry["workflow_id"], workflow)
        atomic_json(f, state)
        return dict(entry)


def validate_workflow(name, workflow):
    check_artifact(json.dumps(workflow))
    return api("POST", "/api/v2/workflow", {"name": name, "workflow": workflow}, dryRun="true")


def _contains(actual, expected, path=()):
    """Platform adds defaults; compare all candidate fields without requiring their absence."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        # Node names and schema property names are semantic maps, not platform defaults.
        if path and path[-1] in ("nodes", "properties") and actual.keys() != expected.keys():
            return False
        return all(k in actual and _contains(actual[k], v, path + (k,)) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_contains(a, b, path) for a, b in zip(actual, expected))
    return actual == expected


def update_workflow(workflow_id, workflow):
    """Read before writing so retries of a saved or published candidate do not create versions."""
    def read():
        return api("GET", f"/api/v2/workflow/{workflow_id}", workspaceId=workspace_id())["workflow"]["workflow"]
    check_artifact(json.dumps(workflow))
    stored = read()
    ac = dict(stored.get("agent_config") or {})
    ac["llmConfig"] = {**(ac.get("llmConfig") or {}), **AGENT_LLM}
    desired = {**workflow, "agent_config": ac}
    if not _contains(stored, desired):
        api("PUT", f"/api/v2/workflow/{workflow_id}", {"workflow": desired})
        stored = read()
        if not _contains(stored, desired):
            raise RuntimeError("Platform did not retain the candidate workflow; refusing to publish")
    vs = api("GET", f"/api/v2/versions/workflow/{workflow_id}", workspaceId=workspace_id())["versions"]
    newest = max(vs, key=lambda v: v["versionNumber"])
    if not newest.get("isPublished"):
        api("POST", f"/api/v2/versions/workflow/{workflow_id}/publish", {"versionId": newest["id"]})
    return newest["versionNumber"]

def export_workflow(workflow_id, path):
    """Write the workflow as it is on the platform to a file. This file is part of what you submit."""
    w = api("GET", f"/api/v2/workflow/{workflow_id}", workspaceId=workspace_id())["workflow"]
    check_artifact(json.dumps(w))
    atomic_json(path, {"workflow_id": w["id"], "agent_id": w.get("agentId"), "updated_at": w.get("updatedAt"), "workflow": w["workflow"]})
    return path
def create_personas(personas):        return api("POST", "/api/v2/personas", {"personas": personas})
def get_iteration(sim_id, it_id):
    """One iteration with ALL its runs. The route returns 30 runs by default and 100 at most, so this reads page by page."""
    out, off = None, 0
    while True:
        r = api("GET", f"/api/v2/simulations/{sim_id}/iterations/{it_id}", limit=100, offset=off)
        if out is None: out = r
        else: out["runs"] += r["runs"]
        off += 100
        if len(r["runs"]) < 100: return out
def get_call(call_id):
    """One simulated call: `messages` holds the transcript, tool calls included. Run ids and call ids come from get_iteration()['runs']."""
    return api("GET", f"/api/v2/call/{call_id}")["call"]

# The model every team's phone agent runs on: Freya's model on the event's own GPU box. Do not change it. (Organisers can point a test at another model with the two variables.)
AGENT_LLM = {"provider": os.environ.get("FREYA_AGENT_PROVIDER", "experimental-5"), "model": os.environ.get("FREYA_AGENT_MODEL", "experimental-5")}
SIM_LLM = {"provider": "google", "model": "gemini-3-flash-preview"}        # plays the customer and judges

def run_simulation(agent_id, name, variables_by_persona, max_seconds=420, concurrency=int(os.environ.get("FREYA_SIM_CONCURRENCY", "5"))):
    """Start a text simulation, wait for it, return (simulation_id, iteration_id)."""
    with runcontrol.deadline(90):
        busy_until = time.monotonic() + 90
        while True:                      # bounded workspace contention wait
            try:
                sim = api("POST", "/api/v2/simulations", {
                    "agentId": agent_id, "name": name, "mode": "chat", "selectedPersonaIds": list(variables_by_persona),
                    "customerVariablesMap": variables_by_persona, "maxConcurrentCalls": concurrency, "runsPerPersona": 1, "maxCallDurationSeconds": max_seconds,
                    "assistantLlmOverride": AGENT_LLM, "routingLlmOverride": AGENT_LLM, "extractionLlmOverride": AGENT_LLM,
                    "personaLlmOverride": SIM_LLM, "analysisLlmOverride": SIM_LLM})
                break
            except RuntimeError as e:
                if "concurrent simulations" not in str(e): raise
                if time.monotonic() >= busy_until:
                    raise TimeoutError("simulation slot busy for 90 seconds") from e
                inherited_event("simulation_wait", remaining_s=round(busy_until - time.monotonic(), 1))
                runcontrol.sleep(min(30, busy_until - time.monotonic()))
    sim_id = (sim.get("simulation") or sim)["id"]
    poll_until = time.monotonic() + max(900, max_seconds * len(variables_by_persona))
    while True:
        if time.monotonic() >= poll_until:
            raise TimeoutError("simulation polling deadline exceeded")
        runcontrol.sleep(10)
        s = api("GET", f"/api/v2/simulations/{sim_id}"); s = s.get("simulation") or s
        if s.get("status") in ("completed", "failed", "paused"): break
    its = api("GET", f"/api/v2/simulations/{sim_id}/iterations"); its = its.get("iterations") or its.get("items") or its
    return sim_id, its[0]["id"], s.get("status")
