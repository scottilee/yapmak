"""OpenAPI normalization and response-field mapping for the compiler."""
import json
import ipaddress
import re
import unicodedata

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
                        if key == "allOf" and merged.get("enum"):
                            merged["enum"] = [x for x in merged["enum"] if x in vs["enum"]]           # every allOf branch must hold: intersect
                        else:
                            merged["enum"] = list(dict.fromkeys(list(merged.get("enum") or []) + list(vs["enum"])))   # oneOf/anyOf: union
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
        text = f.read()
    try:
        spec = json.loads(text)
    except ValueError:
        try:
            import yaml                      # a YAML tool API file (the kit's is JSON; PyYAML is optional)
            spec = yaml.safe_load(text)
        except ImportError as e:
            raise ValueError(f"{path}: not JSON and PyYAML is not installed to read YAML") from e
    if not isinstance(spec, dict) or "paths" not in spec:
        raise ValueError(f"{path}: not an OpenAPI document (no 'paths')")
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
            loopback = parsed.hostname in ("127.0.0.1", "localhost", "::1")      # a local stand-in for rehearsals only; the engine cannot reach it
            if (parsed.scheme != "https" and not (loopback and parsed.scheme == "http")) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or "{" in base:
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
    "customer_id":     (("customer_id", "customer", "client", "member", "holder", "cust", "debtor", "ref"), ("product", "facility", "account", "promise", "note", "item", "loan", "queue")),
    "verify_identity": {"field": (("field", "question", "check", "item", "kind", "type"), ("answer", "value", "customer")),
                        "answer": (("answer", "value", "response", "reply", "given"), ("customer", "field"))},
    "create_promise":  {"product_id": (("product_id", "facility_id", "account_id", "obligation", "product", "facility", "account", "loan", "_id", "id"), ("customer", "client", "member", "promise_id")),
                        "amount": (("amount", "amt", "sum", "value", "promised", "total", "payment", "money"), ("date", "day", "product", "customer")),
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


def _hint(hints: dict | None, key: str, props: dict) -> str:
    """The documents' own statement of a field name ("<tool>.<slot>": property), honoured only when that property exists there."""
    h = (hints or {}).get(key)
    return h if isinstance(h, str) and h in props else ""


def request_slots(tools: dict[str, ToolSpec], hints: dict | None = None) -> dict[str, dict[str, str]]:
    """{tool: {semantic argument: actual body property}}. A field name the documents state (`hints`, policy `api_fields`)
    wins when the schema has it; then the semantic name itself; otherwise the first property matching a needle. A required
    argument that maps to nothing stops the build with the actual property names; `customer_id` is sent only when the
    schema has such a field."""
    out, missing = {}, []
    # the customer field: get_account's body usually has exactly one property, and that name recurs in every tool
    cust_anchor = ""
    ga = tools.get("get_account")
    if ga and len(ga.body_props) == 1:
        cust_anchor = next(iter(ga.body_props))
    order = ["get_account", "verify_identity", "create_promise", "schedule_callback", "add_note", "transfer_to_agent", "close_call"]
    anchors: dict = {}      # semantic argument -> names already found for it in other tools (the same name means the same thing)
    for name in sorted(tools, key=lambda n: order.index(n) if n in order else 99):
        t = tools[name]
        props = t.body_props
        m = {}
        needles, excl = REQUEST_SLOTS["customer_id"]
        m["customer_id"] = (("customer_id" if "customer_id" in props else "") or (cust_anchor if cust_anchor in props else "")
                            or _slot(hints, name + ".customer_id", props, *needles, default="", exclude=excl))
        reserved = {other for other in REQUEST_SLOTS.get(name, {}) if other in props}   # a property named like another argument is that argument
        for sem, (needles, excl) in REQUEST_SLOTS.get(name, {}).items():
            free = {k: v for k, v in props.items() if k not in m.values() and (k == sem or k not in reserved)}
            actual = sem if sem in props else _slot(hints, f"{name}.{sem}", free, *needles, default="", exclude=excl)
            m[sem] = actual
        _request_fallback(name, props, m, anchors)
        for sem, actual in m.items():
            if actual:
                anchors.setdefault(sem, set()).add(actual)
        for sem in REQUEST_SLOTS.get(name, {}):
            if not m.get(sem) and (name, sem) not in OPTIONAL_REQUEST_SLOTS:
                missing.append(f"{name}.{sem} (body has {sorted(props)})")
        out[name] = m
    if missing:
        raise SystemExit("cannot map request fields from the tool API: " + "; ".join(missing))
    return out


def unmapped_request_slots(tools: dict[str, ToolSpec], hints: dict | None = None) -> list[str]:
    """The request arguments no rule could name (the extractor asks the documents / schema for them as api_fields)."""
    try:
        request_slots(tools, hints)
        return []
    except SystemExit as e:
        return [part.split(" (")[0] for part in str(e).split(": ", 1)[1].split("; ")]


def _request_fallback(name: str, props: dict, m: dict, anchors: dict | None = None) -> None:
    """Last resort when names and descriptions say nothing: a name already found for the same argument in another tool
    (create_promise's product and date, add_note's reason) is taken first; then the remaining body properties by type and
    position (schema order mirrors the practice API's argument order). Every assignment is recorded for the trace."""
    def free():
        return [k for k in props if k not in m.values()]
    def take(sem, k):
        if k and not m.get(sem):
            m[sem] = k
            MAPPING_NOTES.append({"tool": name, "slot": sem, "chosen": k, "by": "type/position fallback"})
    for sem in REQUEST_SLOTS.get(name, {}):
        if not m.get(sem):
            hit = [k for k in free() if k in (anchors or {}).get(sem, set())]
            if hit:
                m[sem] = hit[0]
                MAPPING_NOTES.append({"tool": name, "slot": sem, "chosen": hit[0], "by": "same name as in another tool"})
    def typed(ty, fmt=None, enum=None):
        out = []
        for k in free():
            v = props[k] if isinstance(props[k], dict) else {}
            if ty and v.get("type") != ty:
                continue
            if fmt and v.get("format") != fmt and fmt not in _norm(k):
                continue
            if enum is True and "enum" not in v:
                continue
            if enum is False and "enum" in v:
                continue
            out.append(k)
        return out
    if name == "verify_identity":
        strings = typed("string")
        if not m.get("field"):
            take("field", (typed("string", enum=True) or strings or [""])[0])
        strings = typed("string")
        if not m.get("answer"):
            take("answer", (strings or [""])[0])
    elif name == "create_promise":
        if not m.get("amount"):
            take("amount", (typed("number") or typed("integer") or [""])[0])
        if not m.get("date"):
            take("date", (typed("string", fmt="date") or [""])[0])
        if not m.get("product_id"):
            take("product_id", (typed("string", enum=False) or typed("string") or [""])[0])
        if not m.get("date"):
            take("date", (typed("string") or [""])[0])
    elif name == "add_note":
        if not m.get("reason"):
            take("reason", (typed("string", enum=True) or [""])[0])
        if not m.get("product_id"):
            take("product_id", (typed("string", enum=False) or [""])[0])
        if not m.get("text"):
            take("text", (typed("string", enum=False) or [""])[0])
    elif name == "schedule_callback":
        if not m.get("date"):
            take("date", (typed("string", fmt="date") or [""])[0])
        if not m.get("time"):
            take("time", (typed("string", fmt="time") or [""])[0])
        if not m.get("date"):
            take("date", (typed("string") or [""])[0])
        if not m.get("time"):
            take("time", (typed("string") or [""])[0])
    elif name == "transfer_to_agent":
        if not m.get("queue"):
            take("queue", (typed("string", enum=True) or typed("string") or [""])[0])
    elif name == "close_call":
        if not m.get("outcome"):
            take("outcome", (typed("string", enum=True) or typed("string") or [""])[0])
        if not m.get("reason"):
            take("reason", (typed("string", enum=True) or typed("string") or [""])[0])


def request_aliases(tools: dict[str, ToolSpec], R: dict[str, dict[str, str]]) -> dict[str, dict[str, list[str]]]:
    """{tool: {semantic argument: [extra body names]}}: a `required` name the schema lists without a property of that name
    (e.g. properties say `sum`, required says `amt`) is sent as well, with the same value, so a validator reading either
    list is satisfied. Only names that mean one of our arguments (by needle) are added; others are left to the trace."""
    out = {}
    for name, t in tools.items():
        extra = {}
        for req in t.required or []:
            if req in t.body_props or req in R[name].values():
                continue
            for sem, (needles, excl) in list(REQUEST_SLOTS.get(name, {}).items()) + [("customer_id", REQUEST_SLOTS["customer_id"])]:
                if R[name].get(sem) and (req == sem or _pick({req: {}}, *needles, default="", exclude=excl)):
                    extra.setdefault(sem, []).append(req)
                    MAPPING_NOTES.append({"tool": name, "required_without_property": req, "sent_as_alias_of": sem})
                    break
            else:
                MAPPING_NOTES.append({"tool": name, "required_without_property": req, "sent_as_alias_of": None})
        out[name] = extra
    return out


def tool_enums(tools: dict[str, ToolSpec], hints: dict | None = None, strict: bool = True) -> dict[str, dict[str, list[str]]]:
    """Enums keyed by the template's semantic argument names (what the policy IR refers to), resolved through request_slots.
    strict=False (the extractor, before the documents have been read) keeps the mapped arguments and leaves the rest out."""
    try:
        R = request_slots(tools, hints)
    except SystemExit:
        if strict:
            raise
        R = {}
        for name, t in tools.items():
            m = {}
            for sem, (needles, excl) in REQUEST_SLOTS.get(name, {}).items():
                m[sem] = sem if sem in t.body_props else _slot(hints, f"{name}.{sem}", {k: v for k, v in t.body_props.items() if k not in m.values()}, *needles, default="", exclude=excl)
            R[name] = m
    return {n: {sem: t.body_props[actual]["enum"] for sem, actual in R[n].items() if actual and "enum" in t.body_props.get(actual, {})}
            for n, t in tools.items()}


MAPPING_NOTES: list = []   # ambiguous or fallback field mappings for the build trace

# Other-language names for the semantic needles (the brief page says field names can change; a hidden API may not be English).
# Keyed by the first (canonical) needle of a slot; applied in the name round after the English needles.
SYNONYMS = {
    "amount": ("importe", "monto", "cantidad", "suma", "montant", "betrag", "valor", "importo", "bedrag", "kwota"),
    "date": ("fecha", "data", "datum", "jour", "dia", "giorno", "tag", "dag"),
    "time": ("hora", "heure", "uhrzeit", "ora", "tijd", "uhr", "horario", "orario"),
    "product_id": ("contrato", "producto", "produit", "produkt", "prodotto", "cuenta", "compte", "konto", "conta", "contratto", "vertrag"),
    "field": ("pregunta", "frage", "domanda", "vraag", "campo", "champ", "feld"),
    "answer": ("respuesta", "reponse", "antwort", "risposta", "antwoord", "resposta"),
    "reason": ("motivo", "razon", "raison", "grund", "motif", "reden", "causa", "ragione", "codigo", "code"),
    "text": ("texto", "texte", "nota", "notiz", "testo", "tekst", "comentario", "commentaire", "kommentar", "observacion"),
    "queue": ("cola", "fila", "equipe", "equipo", "warteschlange", "coda", "wachtrij", "destino", "destination", "abteilung", "departamento"),
    "outcome": ("resultado", "resultat", "ergebnis", "risultato", "esito", "resultaat", "desenlace", "cierre", "disposicion"),
    "customer_id": ("cliente", "kunde", "klant", "deudor", "debiteur", "schuldner", "titular", "titulaire", "inhaber"),
    "type": ("clase", "tipo", "typ", "art", "categoria", "catégorie", "soort", "genre", "produkttyp"),
    "past_due": ("saldo", "deuda", "dette", "schuld", "vencido", "atraso", "atrasado", "impago", "debito", "mora", "pendiente", "restante", "offen", "achterstand", "scaduto"),
    "days_late": ("dias", "jours", "tage", "giorni", "dagen", "retraso", "retard", "verzug", "ritardo"),
    "list": ("cartera", "productos", "produits", "produkte", "prodotti", "cuentas", "contas", "comptes", "konten", "contratos", "lista", "posiciones"),
    "ok": ("exito", "erfolg", "successo", "succes", "sucesso", "correcto", "valido", "gueltig", "riuscito"),
    "verified": ("verificado", "verifie", "verifiziert", "verificato", "geverifieerd", "correcta", "acierto", "valida", "bestanden", "superada"),
    "remaining": ("restantes", "intentos", "tentatives", "versuche", "tentativi", "pogingen", "tries", "quedan", "verbleibend"),
}


_LAST: dict = {"round": ""}   # how the most recent _pick() found its property: "name" (exact or English word), "synonym", "description", ""


def _slot(hints: dict | None, key: str, props: dict, *needles: str, default: str = "", exclude: tuple = ()) -> str:
    """Needle mapping first; a field name the documents state (hints) replaces it only when the needles found nothing or
    found it weakly (synonym / description round). An exact or English-word match is never overridden: the extractor's
    stated names were wrong on 2 of 32 entries in a test package, the needles were not."""
    k = _pick(props, *needles, default=default, exclude=exclude)
    h = _hint(hints, key, props)
    if h and h != k and (not k or _LAST["round"] not in ("name",)):
        MAPPING_NOTES.append({"slot": key, "chosen": h, "instead_of": k, "by": "stated in the documents"})
        return h
    return k


def _norm(text: str) -> str:
    """Lower-case snake_case without accents: 'pastDueAmount' -> 'past_due_amount', 'Días' -> 'dias'."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", t)
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def _hit(needle: str, text: str) -> bool:
    """The needle starts a word of the normalised text ('days' hits 'dl_days' and 'days_o', not 'holidays';
    a needle written '_id' needs a word before it, so 'id' alone or 'identity' do not count)."""
    core = _norm(needle.strip("_"))
    if not core:
        return False
    pre = r"(?<=[a-z0-9]_)" if needle.startswith("_") else r"(?:^|(?<=_))"
    return re.search(pre + re.escape(core), text) is not None


def _pick(props: dict, *needles: str, default: str = "", exclude: tuple = (), desc: bool = True) -> str:
    """The property that means one of the needles (needles in priority order):
    1. a property named exactly like a needle; 2. a needle starting a word of the (normalised) name, English needles
    first then the other-language synonyms; 3. a needle starting a word of the property's description.
    Names containing an excluded word are skipped in rounds 1-2 (descriptions are not filtered: they mention other fields).
    Several hits for one needle -> the first in schema order is used and the ambiguity is recorded."""
    names = {k: _norm(k) for k in props}
    ok_name = {k for k in props if not any(_hit(x, names[k]) or x in names[k] for x in exclude)}
    _LAST["round"] = ""
    def choose(n, hits, where):
        _LAST["round"] = where
        if len(hits) > 1:
            MAPPING_NOTES.append({"needle": n, "chosen": hits[0], "also": hits[1:], "by": where})
        elif where != "name":
            MAPPING_NOTES.append({"needle": n, "chosen": hits[0], "by": where})
        return hits[0]
    for n in needles:
        hits = [k for k in props if names[k] == _norm(n) and k in ok_name]
        if hits:
            return choose(n, hits, "name")
    for n in needles:
        hits = [k for k in props if k in ok_name and _hit(n, names[k])]
        if hits:
            return choose(n, hits, "name")
    for n in needles:
        for syn in SYNONYMS.get(n, ()):
            hits = [k for k in props if k in ok_name and _hit(syn, names[k])]
            if hits:
                return choose(syn, hits, "synonym")
    if desc:
        descs = {k: _norm(str((v or {}).get("description") or "")) if isinstance(v, dict) else "" for k, v in props.items()}
        for n in needles:
            hits = [k for k in props if descs[k] and _hit(n, descs[k])]
            if hits:
                return choose(n, hits, "description")
    return default


def _response_fallback(slots: dict, v: dict, items: dict, tools: dict) -> None:
    """Last resort by type when names and descriptions say nothing (recorded for the trace)."""
    def note(slot, k, where):
        MAPPING_NOTES.append({"slot": slot, "chosen": k, "by": where})
        return k
    def typed(props, ty, used=(), enum=None):
        return [k for k, s in props.items() if isinstance(s, dict) and s.get("type") == ty and k not in used and (enum is None or (("enum" in s) is enum))]
    A, V = slots["account"], slots["verify"]
    used = {x for x in A.values() if x}
    if not A["type"]:
        c = typed(items, "string", used, enum=True)
        if c:
            A["type"] = note("get_account.type", c[0], "type fallback: the enumerated string"); used.add(c[0])
    if not A["id"]:
        c = typed(items, "string", used, enum=False)
        if c:
            A["id"] = note("get_account.id", c[0], "type fallback: the free string"); used.add(c[0])
    if not A["days_late"]:
        c = typed(items, "integer", used)
        if c:
            A["days_late"] = note("get_account.days_late", c[0], "type fallback: the integer"); used.add(c[0])
    if not A["past_due"]:
        c = typed(items, "number", used) or typed(items, "integer", used)
        if c:
            A["past_due"] = note("get_account.past_due", c[0], "type fallback: the first number"); used.add(c[0])
    bools = typed(v, "boolean")
    shared = [b for b in bools if all(b in t.response_props for t in tools.values())]     # the one success flag every tool returns
    if not V["ok"] and shared:
        V["ok"] = note("verify_identity.ok", shared[0], "type fallback: the boolean every tool returns")
    if not V["ok"] and bools:
        V["ok"] = note("verify_identity.ok", bools[0], "type fallback: the first boolean")
    if not V["verified"]:
        rest = [b for b in bools if b != V["ok"]]
        if rest:
            V["verified"] = note("verify_identity.verified", rest[0], "type fallback: the second boolean")
    if not V["all_verified"]:
        rest = [b for b in bools if b not in (V["ok"], V["verified"])]
        if rest:
            V["all_verified"] = note("verify_identity.all_verified", rest[0], "type fallback: the third boolean")
    if not V["remaining"]:
        ints = typed(v, "integer")
        if ints:
            V["remaining"] = note("verify_identity.remaining", ints[0], "type fallback: the integer")
    for n, t in tools.items():
        if not slots["ok_by_tool"].get(n):
            b = typed(t.response_props, "boolean")
            sh = [x for x in b if all(x in tt.response_props for tt in tools.values())]
            if sh or b:
                slots["ok_by_tool"][n] = note(n + ".ok", (sh or b)[0], "type fallback: the boolean every tool returns" if sh else "type fallback: the first boolean")


def response_slots(tools: dict[str, ToolSpec], hints: dict | None = None) -> dict:
    """Map the response properties of the supplied OpenAPI document onto the template's semantic slots.
    A field name the documents state (`hints`, policy `api_fields`, e.g. "get_account.past_due": "outst") wins when the
    schema has it; otherwise names are matched by meaning (substrings), never assumed from the practice kit."""
    v = tools["verify_identity"].response_props
    g = tools["get_account"].response_props

    def find_list(props, prefix=""):
        """The product array: at the top level, or nested in an envelope object ('payload.products'); dotted path."""
        for k, spec in props.items():
            if isinstance(spec, dict) and spec.get("type") == "array" and isinstance((spec.get("items") or {}).get("properties"), dict):
                return prefix + k, spec["items"]["properties"]
        for k, spec in props.items():
            if isinstance(spec, dict) and spec.get("type") == "object" and isinstance(spec.get("properties"), dict):
                found = find_list(spec["properties"], prefix + k + ".")
                if found:
                    return found
        return None
    stated = _hint(hints, "get_account.list", g)
    found = find_list(g)
    if stated and stated in g and isinstance((g[stated].get("items") or {}).get("properties"), dict):
        list_prop, items = stated, g[stated]["items"]["properties"]
    elif found:
        list_prop, items = found
        if "." in list_prop:
            MAPPING_NOTES.append({"slot": "get_account.list", "chosen": list_prop, "by": "nested in a response envelope"})
    else:
        list_prop = _slot(hints, "get_account.list", g, "products", "accounts", "facilities", "items", default="products")
        items = g.get(list_prop, {}).get("items", {}).get("properties", {})
    slots = {
        "verify": {
            "ok": _slot(hints, "verify_identity.ok", v, "ok", "success", "accepted", "succeeded", "executed", "completed", "status", default="", exclude=("all_", "verified", "match", "remaining", "left", "hint", "error")),
            "verified": next((k for k in v if "verified" in k and not k.startswith("all")), "") or _slot(hints, "verify_identity.verified", v, "verified", "answer", "match", "correct", "passed", "this", default="", exclude=("all", "identity", "fully", "complete")),
            "all_verified": _slot(hints, "verify_identity.all_verified", v, "all_verified", "all", "identity", "complete", "fully", default="", exclude=("answer", "question", "attempt", "tries", "left")),
            "remaining": _slot(hints, "verify_identity.remaining", v, "left", "remaining", "attempts", "tries", default=""),
            "hint": _slot(hints, "verify_identity.hint", v, "hint", default=""),
        },
        "account": {
            "list": list_prop or "",
            "id": _slot(hints, "get_account.id", items, "product_id", "facility_id", "account_id", "_id", "_ref", "reference", "identifier", "id", "ref", default="",
                        exclude=("customer", "client", "member", "holder")),
            "type": _slot(hints, "get_account.type", items, "type", "kind", "category", "class", "product", "facility", "account", "cat", default="",
                          exclude=("_id", "_ref", "amount", "days", "minimum", "floor", "instalment", "last4", "located", "allocat")),
            "past_due": _slot(hints, "get_account.past_due", items, "past_due", "arrears", "outstanding", "outst", "overdue", "due", "balance", "owed", "owing", "amount", "bal", default="",
                              exclude=("minimum", "min_", "scheduled", "instalment", "installment", "repayment", "days", "late", "since", "count")),
            "days_late": _slot(hints, "get_account.days_late", items, "days_late", "days", "late", "overdue_since", "dpd", "delinq", default="", exclude=("amount", "balance")),
            "card_last4": _slot(hints, "get_account.card_last4", items, "last4", "last_4", "last_four", default=""),
        },
        # the success flag of every write tool, per tool (the template routes on it after each engine-fired call)
        "ok_by_tool": {n: _slot(hints, n + ".ok", t.response_props, "ok", "success", "accepted", "succeeded", "executed", "completed", "status", default="",
                                exclude=("all_", "verified", "match", "remaining", "left", "hint", "error", "_id", "products", "items")) for n, t in tools.items()},
    }
    _response_fallback(slots, v, items, tools)
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
