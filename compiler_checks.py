"""Static checks for emitted workflows."""
from compiler_openapi import ToolSpec

BANK_TOOLS = ("verify_identity", "get_account", "create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call")


def static_check(wf: dict, tools: dict[str, ToolSpec]) -> list[str]:
    errs = []
    nodes = wf.get("nodes", {})
    if wf.get("initial_node") not in nodes:
        errs.append("initial_node missing")
    if "agent_config" in wf or "context_variables" in wf:
        errs.append("agent_config/context_variables must be omitted")

    def walk(o, path="workflow"):
        if o is None:
            errs.append(f"null value at {path}")
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    walk(wf)
    for name, n in nodes.items():
        t = n.get("node_type")
        for tr in n.get("transitions", []):
            if tr["target_node"] not in nodes and tr["target_node"] != "__previous__":
                errs.append(f"{name}: transition to unknown node {tr['target_node']}")
        if t == "conversation":
            if n.get("tools"):
                errs.append(f"{name}: conversation node must not carry tools (bank tools are engine-fired)")
            if "pre_actions" in n:
                errs.append(f"{name}: pre_actions on a conversation node are dropped by the platform")
            if not n.get("max_node_turns") or not n.get("max_turn_transition"):
                errs.append(f"{name}: needs max_node_turns and max_turn_transition")
            for e in n.get("extraction_schema", []):
                if "min_confidence" not in e:
                    errs.append(f"{name}: extraction {e['name']} without min_confidence")
        elif t in ("code", "api_request"):
            if "tools" in n:
                errs.append(f"{name}: tools on a non-conversation node are dropped")
            if not n.get("passthrough") or not n.get("passthrough_default_transition"):
                errs.append(f"{name}: passthrough node needs passthrough_default_transition")
            if not n.get("transitions") or n["transitions"][-1]["condition"].get("operator") != "always":
                errs.append(f"{name}: passthrough node must end with an always transition")
            for pa in n.get("pre_actions", []):
                fn = pa["function"]
                if fn["handler"] == "__function__:code_exec":
                    code = fn["parameters"]["properties"]["code"]["default"]
                    if "{{" in code or "}}" in code:
                        errs.append(f"{name}: code contains template braces")
                    try:
                        compile(code, name, "exec")
                    except SyntaxError as e:
                        errs.append(f"{name}: code does not compile: {e}")
                elif fn["handler"] == "__function__:api_call":
                    body = fn["parameters"]["properties"]["body"]
                    spec = next((s for s in tools.values() if s.url == fn["parameters"]["properties"]["url"]["default"]), None)
                    if spec is None:
                        errs.append(f"{name}: url not in OpenAPI")
                    else:
                        for req in spec.required:
                            if req not in body["properties"]:
                                errs.append(f"{name}: required field {req} missing")
                        for field, prop in body["properties"].items():
                            if field not in spec.body_props:
                                errs.append(f"{name}: body field {field} not in OpenAPI")
                            if "default" not in prop:
                                errs.append(f"{name}: body field {field} has no baked default")
                            lit = prop["default"]
                            if "enum" in spec.body_props.get(field, {}) and not str(lit).startswith("{{") and lit not in spec.body_props[field]["enum"]:
                                errs.append(f"{name}: {field}={lit} not in enum")
                    if pa.get("config", {}).get("maxRetries", 0) and fn["name"] in ("create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call"):
                        errs.append(f"{name}: write tool with retries")
        elif t == "end_call":
            if n.get("transitions"):
                errs.append(f"{name}: end node with transitions")
    # reachability of an end node
    seen, stack = set(), [wf.get("initial_node")]
    while stack:
        x = stack.pop()
        if x in seen or x not in nodes:
            continue
        seen.add(x)
        for tr in nodes[x].get("transitions", []):
            stack.append(tr["target_node"])
        if nodes[x].get("max_turn_transition"):
            stack.append(nodes[x]["max_turn_transition"])
    if not any(nodes[x].get("node_type") == "end_call" for x in seen):
        errs.append("no end_call node reachable")
    for x in nodes:
        if x not in seen:
            errs.append(f"unreachable node {x}")
    return errs


IGNORED_TOP = {"agent_config", "nodePositions", "test_variables", "tools", "context_variables"}


def workflow_diff(candidate: dict, stored: dict, path: str = "", out: list | None = None) -> list[str]:
    """Compare the workflow we sent with what the platform stored (it strips and adds fields silently).
    Same semantics as the rehearsal tool's diff; shared so build.py can log it in the trace."""
    if out is None:
        out = []
    if isinstance(candidate, dict) and isinstance(stored, dict):
        for k in set(candidate) | set(stored):
            if path == "" and k in IGNORED_TOP:
                continue
            if k not in stored:
                out.append(f"{path}.{k}: missing in stored")
            elif k not in candidate:
                out.append(f"{path}.{k}: added by platform")
            else:
                workflow_diff(candidate[k], stored[k], f"{path}.{k}", out)
    elif isinstance(candidate, list) and isinstance(stored, list):
        if len(candidate) != len(stored):
            out.append(f"{path}: list length {len(candidate)} -> {len(stored)}")
        for i, (x, y) in enumerate(zip(candidate, stored)):
            workflow_diff(x, y, f"{path}[{i}]", out)
    elif candidate != stored and not (candidate in ("", None, False) and stored in ("", None, False)):
        out.append(f"{path}: {str(candidate)[:60]!r} -> {str(stored)[:60]!r}")
    return out
