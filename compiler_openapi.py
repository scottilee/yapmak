"""OpenAPI normalization and response-field mapping for the compiler."""
import json
import ipaddress
import re

class ToolSpec:
    def __init__(self, name, url, method, body_props, required, response_props):
        self.name, self.url, self.method = name, url, method
        self.body_props, self.required, self.response_props = body_props, required, response_props

    def enums(self):
        return {k: v["enum"] for k, v in self.body_props.items() if "enum" in v}


def _resolve(value, document, stack=()):
    """Resolve local JSON pointers; reject remote/cyclic schemas explicitly."""
    if isinstance(value, list):
        return [_resolve(v, document, stack) for v in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        ref = value["$ref"]
        if not ref.startswith("#/") or ref in stack:
            raise ValueError(f"unsupported external or recursive OpenAPI reference: {ref}")
        target = document
        try:
            for part in ref[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            raise ValueError(f"unresolved OpenAPI reference: {ref}") from None
        resolved = _resolve(target, document, stack + (ref,))
        return {**resolved, **_resolve({k: v for k, v in value.items() if k != "$ref"}, document, stack)}
    if any(k in value for k in ("allOf", "oneOf", "anyOf")):
        return _flatten_composition({k: _resolve(v, document, stack) for k, v in value.items()})
    return {k: _resolve(v, document, stack) for k, v in value.items()}


def _flatten_composition(schema: dict) -> dict:
    """Collapse allOf/oneOf/anyOf into one object schema the template can bake bodies against. Base `properties` stay;
    variant properties are merged in (enums united, new fields added). `allOf` adds every variant's `required`; `oneOf`/`anyOf`
    keep only fields required by every variant (the base `required` always stays). `not` constraints are dropped: the policy
    decides which fields a given outcome carries (e.g. no reason for reasonless outcomes)."""
    out = {k: v for k, v in schema.items() if k not in ("allOf", "oneOf", "anyOf", "not")}
    props = dict(out.get("properties") or {})
    required = list(out.get("required") or [])
    for key in ("allOf", "oneOf", "anyOf"):
        variants = [v for v in schema.get(key) or [] if isinstance(v, dict)]
        if not variants:
            continue
        variants = [_flatten_composition(v) if any(c in v for c in ("allOf", "oneOf", "anyOf")) else v for v in variants]
        for v in variants:
            for name, vs in (v.get("properties") or {}).items():
                if name in props and isinstance(props[name], dict) and isinstance(vs, dict):
                    merged = dict(props[name])
                    if "enum" in vs:
                        merged["enum"] = list(dict.fromkeys(list(merged.get("enum") or []) + list(vs["enum"])))
                    for k2, v2 in vs.items():
                        if k2 not in merged:
                            merged[k2] = v2
                    props[name] = merged
                else:
                    props[name] = vs
        if key == "allOf":
            for v in variants:
                required += [r for r in v.get("required") or [] if r not in required]
        else:
            common = set.intersection(*(set(v.get("required") or []) for v in variants)) if variants else set()
            required += [r for r in sorted(common) if r not in required]
        if "type" not in out:
            out["type"] = next((v.get("type") for v in variants if v.get("type")), "object")
    out["properties"] = props
    if required:
        out["required"] = required
    return out


def parse_openapi(path: str) -> dict[str, ToolSpec]:
    from urllib.parse import urlsplit
    with open(path) as f:
        spec = json.load(f)
    tools = {}
    bank_origin = None
    bank_tools = {"verify_identity", "get_account", "create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call"}
    for p, raw_ops in spec["paths"].items():
        ops = _resolve(raw_ops, spec)
        for method, op in ops.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}:
                continue  # parameters, servers, summary, description, extensions are not operations
            name = op.get("operationId") or p.strip("/").split("/")[-1]
            if name in tools:
                raise ValueError(f"duplicate OpenAPI operationId: {name}")
            servers = op.get("servers") or ops.get("servers") or spec.get("servers") or []
            base = servers[0]["url"].rstrip("/") if servers else ""
            parsed = urlsplit(base)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or "{" in base:
                raise ValueError(f"{name}: expected an absolute HTTPS server without credentials or variables")
            host = parsed.hostname
            try:
                ipaddress.ip_address(host)
            except ValueError:
                labels = host.rstrip(".").encode("idna").decode("ascii").split(".")
                if len(host) > 253 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels):
                    raise ValueError(f"{name}: malformed server hostname")
            origin = (parsed.scheme, host.lower().rstrip("."), parsed.port or 443)
            if name in bank_tools:
                if bank_origin is not None and origin != bank_origin:
                    raise ValueError(f"{name}: bank tools must use the same HTTPS origin")
                bank_origin = origin
            if any(c.isspace() for c in base) or "\\" in base:
                raise ValueError(f"{name}: malformed server URL")
            if not p.startswith("/") or "{" in p:
                raise ValueError(f"{name}: parameterized paths are unsupported")
            parameters = ops.get("parameters", []) + op.get("parameters", [])
            if any(param.get("required") for param in parameters):
                raise ValueError(f"{name}: required path/query/header parameters are unsupported")
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            if op.get("requestBody", {}).get("required") and not body:
                raise ValueError(f"{name}: required body must use application/json")
            responses = op.get("responses", {})
            success = [(str(status), response) for status, response in responses.items()
                       if len(str(status)) == 3 and str(status).startswith("2")]
            schemas = [r.get("content", {}).get("application/json", {}).get("schema", {}) for _, r in success]
            if not schemas or not schemas[0] or any(r != schemas[0] for r in schemas[1:]):
                raise ValueError(f"{name}: needs one unambiguous JSON success-response schema")
            resp = schemas[0]
            if not isinstance(body.get("properties", {}), dict) or not isinstance(resp.get("properties"), dict):
                raise ValueError(f"{name}: body and response schemas must be objects")
            tools[name] = ToolSpec(name, base + p, method.upper(), body.get("properties", {}), body.get("required", []), resp["properties"])
    return tools


# Request fields are discovered too (the kit says fields and allowed values can change): each semantic argument the
# template sends is mapped onto the supplied schema's property by meaning. (needles in priority order, excluded words)
REQUEST_SLOTS = {
    "customer_id":     (("customer_id", "customer", "client", "member", "holder", "cust"), ("product", "facility", "account", "promise", "note")),
    "verify_identity": {"field": (("field", "question", "check", "item", "kind", "type"), ("answer", "value", "customer")),
                        "answer": (("answer", "value", "response", "reply", "given"), ("customer", "field"))},
    "create_promise":  {"product_id": (("product_id", "facility_id", "account_id", "obligation", "product", "facility", "account", "loan", "_id", "id"), ("customer", "client", "member", "promise_id")),
                        "amount": (("amount", "sum", "value", "promised", "total", "payment"), ("date", "day", "product", "customer")),
                        "date": (("date", "day", "when", "due", "scheduled"), ("amount", "time", "product", "customer"))},
    "add_note":        {"product_id": (("product_id", "facility_id", "account_id", "obligation", "product", "facility", "account", "loan", "_id", "id"), ("customer", "client", "member", "note_id")),
                        "reason": (("reason", "code", "category", "kind", "type"), ("product", "customer", "text", "note_id")),
                        "text": (("text", "note", "comment", "message", "detail", "body"), ("product", "customer", "reason", "code"))},
    "schedule_callback": {"date": (("date", "day", "when", "_on", "scheduled_for"), ("time", "customer", "client", "_at")),
                          "time": (("time", "hour", "slot", "clock", "_at"), ("date", "day", "customer", "client", "_on"))},
    "transfer_to_agent": {"queue": (("queue", "team", "department", "desk", "destination", "target", "group", "route", "line", "key"), ("customer", "client", "member"))},
    "close_call":      {"outcome": (("outcome", "disposition", "result", "status", "resolution", "closing_code", "code"), ("reason", "sub", "customer", "client")),
                        "reason": (("reason", "sub", "detail", "cause", "code"), ("outcome", "disposition", "result", "status", "customer", "client", "closing_code"))},
}
OPTIONAL_REQUEST_SLOTS = {("add_note", "text"), ("close_call", "reason")}


def request_slots(tools: dict[str, ToolSpec]) -> dict[str, dict[str, str]]:
    """{tool: {semantic argument: actual body property}}. The semantic name itself wins when present; otherwise the first
    property matching a needle. A required argument that maps to nothing stops the build with the actual property names;
    `customer_id` is sent only when the schema has such a field."""
    out, missing = {}, []
    for name, t in tools.items():
        props = t.body_props
        m = {}
        needles, excl = REQUEST_SLOTS["customer_id"]
        m["customer_id"] = "customer_id" if "customer_id" in props else _pick(props, *needles, default="", exclude=excl)
        for sem, (needles, excl) in REQUEST_SLOTS.get(name, {}).items():
            actual = sem if sem in props else _pick({k: v for k, v in props.items() if k not in m.values()}, *needles, default="", exclude=excl)
            if not actual and (name, sem) not in OPTIONAL_REQUEST_SLOTS:
                missing.append(f"{name}.{sem} (body has {sorted(props)})")
            m[sem] = actual
        out[name] = m
    if missing:
        raise SystemExit("cannot map request fields from the tool API: " + "; ".join(missing))
    return out


def tool_enums(tools: dict[str, ToolSpec]) -> dict[str, dict[str, list[str]]]:
    """Enums keyed by the template's semantic argument names (what the policy IR refers to), resolved through request_slots."""
    R = request_slots(tools)
    return {n: {sem: t.body_props[actual]["enum"] for sem, actual in R[n].items() if actual and "enum" in t.body_props.get(actual, {})}
            for n, t in tools.items()}


def _pick(props: dict, *needles: str, default: str = "", exclude: tuple = ()) -> str:
    """First response property whose name contains one of the needles (in order), skipping names with an excluded word."""
    for n in needles:
        for k in props:
            if n in k and not any(x in k for x in exclude):
                return k
    return default


def response_slots(tools: dict[str, ToolSpec]) -> dict:
    """Map the response properties of the supplied OpenAPI document onto the template's semantic slots.
    Names are matched by meaning (substrings), never assumed from the practice kit."""
    v = tools["verify_identity"].response_props
    g = tools["get_account"].response_props
    list_prop = next((k for k, spec in g.items() if spec.get("type") == "array"), None) or _pick(g, "products", "accounts", "facilities", "items", default="products")
    items = g.get(list_prop, {}).get("items", {}).get("properties", {})
    slots = {
        "verify": {
            "ok": _pick(v, "ok", "success", "accepted", "succeeded", "executed", "completed", "status", default="", exclude=("all_", "verified", "match", "remaining", "left", "hint", "error")),
            "verified": next((k for k in v if "verified" in k and not k.startswith("all")), _pick(v, "match", "correct", "passed", default="")),
            "all_verified": _pick(v, "all_verified", "all", "complete", default=""),
            "remaining": _pick(v, "left", "remaining", "attempts", default=""),
            "hint": _pick(v, "hint", default=""),
        },
        "account": {
            "list": list_prop or "",
            "id": _pick(items, "product_id", "facility_id", "account_id", "_id", "_ref", "reference", "identifier", "id", "ref", default="",
                        exclude=("customer", "client", "member", "holder")),
            "type": _pick(items, "type", "kind", "category", "class", "product", "facility", "account", default="",
                          exclude=("_id", "_ref", "amount", "days", "minimum", "floor", "instalment", "last4")),
            "past_due": _pick(items, "past_due", "arrears", "outstanding", "overdue", "due", "balance", "amount", default="",
                              exclude=("minimum", "min_", "scheduled", "instalment", "installment", "repayment", "days", "late", "since", "count")),
            "days_late": _pick(items, "days_late", "days", "late", "overdue_since", default="", exclude=("amount", "balance")),
            "card_last4": _pick(items, "last4", "last_4", "last_four", default=""),
        },
        # the success flag of every write tool, per tool (the template routes on it after each engine-fired call)
        "ok_by_tool": {n: _pick(t.response_props, "ok", "success", "accepted", "succeeded", "executed", "completed", "status", default="",
                                exclude=("all_", "verified", "match", "remaining", "left", "hint", "error", "_id", "products", "items")) for n, t in tools.items()},
    }
    slots["ok"] = slots["ok_by_tool"].get("create_promise", "")
    # enforcement slots: an unmapped one must stop the build (plan §3.2) instead of baking a stock name
    missing = [f"verify_identity.{k}" for k in ("ok", "verified") if not slots["verify"][k]]
    missing += [f"get_account.{k}" for k in ("list", "id", "type", "past_due", "days_late") if not slots["account"][k]]
    missing += [f"{n}.ok" for n in ("create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call") if n in tools and not slots["ok_by_tool"].get(n)]
    if missing:
        raise SystemExit("cannot map response slots from the tool API: " + ", ".join(missing) + f"; verify_identity has {sorted(v)}, {list_prop or 'list'} items have {sorted(items)}")
    if not slots["verify"]["all_verified"]:
        slots["verify"]["all_verified"] = "__none__"      # optional: the runtime falls back to "last question passed"
    if not slots["verify"]["remaining"]:
        slots["verify"]["remaining"] = "__none__"         # optional: the runtime counts wrong answers itself
    if not slots["verify"]["hint"]:
        slots["verify"]["hint"] = "__none__"
    if not slots["account"]["card_last4"]:
        slots["account"]["card_last4"] = "__none__"
    return slots
