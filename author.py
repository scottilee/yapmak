"""Authoring path of the builder: for a case the fixed collections template does not fit, the model writes the workflow itself
from the bank's documents and the mock's OpenAPI, under generic design rules; the builder then validates, repairs, publishes
and exports it exactly as it does for a compiled workflow. Nothing here knows the case: every fact comes from the folder.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import pathlib

import compiler_checks
import extract as X
import policy as P

ROOT = pathlib.Path(__file__).resolve().parent

GUIDANCE = """
DESIGN RULES (generic; every fact about the bank, its services, its customers and its wording comes from the documents):
1. Read EVERY document first, in the order given (the brief and the folder overview first). Documents may disagree; prefer the
   most recent, then the most specific. Record what you could not resolve as a comment in the workflow's top-level "notes" key
   (a string); say nothing invented to the customer.
2. The call variables are exactly those the documents name (e.g. an already-identified customer number and the call time
   `now`). Use them as {{variable}}; never ask the customer for data the phone menu already supplied; never use the system clock
   when the documents say decisions use `now`.
3. Every bank service is called by the ENGINE: an `api_request` node with `pre_actions` (handler __function__:api_call), the exact
   path, method, headers and JSON body field names from the OpenAPI (use {{var:json}} for numbers/objects in bodies), a
   `response_mapping` into variables, and transitions that route on the result (status / a success field). Conversation nodes
   carry `"tools": []`. Call the look-up services as soon as the call starts (passthrough nodes before the first spoken line), so
   the first sentence can already contain the data the documents say the agent reads out.
4. Speak the documents' language, with the exact announcements/phrases the documents dictate where they dictate them; amounts,
   currencies, dates and names come only from variables ({{var}} in prompts; dates are substituted in the agent's language).
   Keep turns short. One question at a time.
5. Every customer intent the documents define gets a clear path: the main question, each optional service (collect what is
   needed, call the service, confirm what the service answered — never confirm before the call succeeded), hand-over to a
   human where the documents say so (via the service or node the documents define), and a goodbye. Unknown requests: the
   documents' refusal/redirect sentence, then back to the main question.
6. Honesty: when a service fails (non-2xx, error field), say the documents' error sentence and offer the alternative the
   documents give; never say something was done when the call did not succeed.
7. Routing: deterministic transitions on `extraction_schema` variables with enums (intents) and on call results; put
   deterministic conditions before `matches_intent`; passthrough nodes end with an `always` transition; every path reaches an
   `end_call` node (terminal with the farewell in `spoken_message`, `message_mode` "custom"); give every conversation node
   `max_node_turns` and a `max_turn_transition`.
8. Structure: top-level keys `initial_node`, `system_prompt`, `global_nodes`, `nodes`, `test_variables` (defaults for the call
   variables only). Omit `agent_config` and `context_variables`. snake_case node keys. Follow examples/base-agent.json for the exact
   JSON shapes of each node type and docs/workflow-format.md + docs/tools-and-code.md for fields and behaviour.
9. Never put test-customer data, expected answers or scenario scripts into the workflow: the mock serves the data.
10. Prefer rules in routes, code and fixed lines over rules in prompts. Keep the dialogue model's instructions explicit about
    what it may and may not say in each node.
"""


def _readable(briefs, openapi_path):
    return [ROOT / p if not pathlib.Path(p).is_absolute() else pathlib.Path(p) for p in briefs] + [
        ROOT / openapi_path if not pathlib.Path(openapi_path).is_absolute() else pathlib.Path(openapi_path),
        ROOT / "docs/workflow-format.md", ROOT / "docs/tools-and-code.md", ROOT / "examples/base-agent.json"]


def _previous_run(slot: str):
    """run_id and file of the newest archived trace of this slot (the run whose draft is being resumed)."""
    files = sorted((ROOT / "traces").glob(f"{slot}.*.jsonl"), key=lambda f: f.stat().st_mtime)
    for f in reversed(files):
        try:
            first = json.loads(f.read_text().splitlines()[0])
            return first.get("run_id"), str(f.relative_to(ROOT))
        except Exception:
            continue
    return None, None


def author(briefs: list[str], openapi_path: str, slot: str, trace, tools, mock_url: str = "", draft: str | None = None, repair_notes: str | None = None) -> dict:
    out = ROOT / "out" / f"{slot}.workflow.json"
    out.parent.mkdir(exist_ok=True)
    access = dict(cwd=ROOT, readable=_readable(briefs, openapi_path) + [out], writable=[out])
    if draft:
        # resume: the draft was written by the model in an earlier run (its trace is archived under traces/<slot>.<stamp>.<id>.jsonl);
        # only the validation/repair/publish steps run again. Nothing is edited by hand: the draft is used byte for byte.
        src = pathlib.Path(draft) if pathlib.Path(draft).is_absolute() else ROOT / draft
        data = src.read_bytes()
        if src.resolve() != out.resolve():
            out.write_bytes(data)
        run_id, tfile = _previous_run(slot)
        if trace:
            trace.event("authoring_resumed", draft=str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else str(src), draft_sha256_16=hashlib.sha256(data).hexdigest()[:16],
                        draft_mtime_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(src.stat().st_mtime)), authoring_run_id=run_id, authoring_trace=tfile)
    else:
        if out.exists():
            out.unlink()
    docs = "\n".join(f"- {p}" for p in briefs)
    prompt = f"""You are the agent-builder's authoring step. Build a Freya phone-agent workflow for the bank whose documents are listed below.
Documents, in reading order:
{docs}
Tool API (the bank's services as the team's mock serves them; the phone agent calls exactly these): {openapi_path}
Reference: docs/workflow-format.md, docs/tools-and-code.md, examples/base-agent.json (a small working agent: copy its node shapes).
{GUIDANCE}
Work efficiently: read each document once, then write the complete workflow JSON to {out.relative_to(ROOT)} in ONE Write call (aim for
8–15 nodes; no commentary inside the JSON). Write nothing else and run no code. If a document cannot be read, say so and still write
the workflow from what you could read."""
    X.PASS_TIMEOUT_S = max(X.PASS_TIMEOUT_S, 1200)        # authoring reads every document and writes a whole workflow: more than an extraction pass
    if not draft:
        asyncio.run(X._query(prompt, "workflow_authoring", trace, max_turns=80, **access))
    if not out.exists():
        raise RuntimeError("authoring produced no workflow file")
    if repair_notes:
        # live-check feedback: observations from simulated calls of the draft (what was said, which node/variable behaved how); the model
        # decides the changes under the documents and the design rules. The notes file is recorded in the trace and committed with the run.
        npath = pathlib.Path(repair_notes) if pathlib.Path(repair_notes).is_absolute() else ROOT / repair_notes
        notes = npath.read_text()
        if trace:
            trace.event("authoring_live_repair", notes=str(npath.relative_to(ROOT)) if npath.is_relative_to(ROOT) else str(npath), notes_sha256_16=hashlib.sha256(notes.encode()).hexdigest()[:16], chars=len(notes))
        access["readable"] = access["readable"] + [npath]
        fix = f"""The workflow you wrote at {out.relative_to(ROOT)} was published and tested with simulated callers. The observations are in
{npath.relative_to(ROOT) if npath.is_relative_to(ROOT) else npath} (read it first). Revise the workflow so that each observed defect cannot recur, deciding every change from the
documents listed below and from the design rules; keep everything that worked. Re-read docs/workflow-format.md and
docs/tools-and-code.md where the engine's behaviour matters (variables keep their values across nodes unless reset in code; global
nodes are matched by the routing model on every turn in every node not listed in excluded_nodes; extraction enums are matched as
strings). Prefer deterministic routes, counters in code nodes and fixed lines over instructions to the dialogue model.
Documents, in reading order:
{docs}
Tool API: {openapi_path}
{GUIDANCE}
Write the complete corrected JSON back to {out.relative_to(ROOT)} in ONE Write call. Run no code. Write nothing else."""
        asyncio.run(X._query(fix, "workflow_live_repair", trace, max_turns=60, **access))
    wf = json.loads(out.read_text())
    for attempt in range(2):
        errs = compiler_checks.static_check(wf, tools)
        if trace:
            trace.event("authoring_static_check", attempt=attempt, errors=errs[:40])
        if not errs:
            break
        fix = f"""The workflow at {out.relative_to(ROOT)} fails these checks (fix exactly these, keeping everything else; re-read docs/workflow-format.md
and {openapi_path} where needed):
""" + "\n".join("- " + e for e in errs[:60]) + f"\nWrite the corrected full JSON back to {out.relative_to(ROOT)}. Run no code."
        asyncio.run(X._query(fix, "workflow_repair", trace, max_turns=40, **access))
        wf = json.loads(out.read_text())
    X.check_artifact(json.dumps(wf))
    return wf


def fits_template(tools) -> bool:
    """The fixed collections template applies only when the API has the seven collection tools."""
    return {"verify_identity", "get_account", "create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call"} <= set(tools)
