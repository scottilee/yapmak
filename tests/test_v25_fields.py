"""v25: stated field names (policy api_fields), required-without-property aliases, abbreviation needles, allOf enum intersection."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import compiler_openapi as CO  # noqa: E402
import policy as P  # noqa: E402


def _tools(path):
    return CO.parse_openapi(str(path))


def test_required_without_property_is_sent_as_alias():
    tools = _tools(ROOT / "tests/fixtures/external/harwick-lowe-register/openapi.json")
    R = CO.request_slots(tools)
    assert R["create_promise"]["amount"] == "sum"
    AL = CO.request_aliases(tools, R)
    assert AL["create_promise"]["amount"] == ["amt"]
    assert not AL["close_call"]


def test_abbreviated_response_names_map_by_needle():
    tools = _tools(ROOT / "tests/fixtures/external/harwick-lowe-register/openapi.json")
    S = CO.response_slots(tools)
    assert S["account"] == {"list": "facilities", "id": "facility_id", "type": "cat", "past_due": "outst", "days_late": "days_o", "card_last4": "__none__"}


def test_stated_field_names_win_only_when_present():
    tools = _tools(ROOT / "tools/openapi.json")
    S = CO.response_slots(tools, {"get_account.past_due": "nonexistent", "get_account.type": "type"})
    base = CO.response_slots(tools)
    assert S == base
    R = CO.request_slots(tools, {"create_promise.amount": "date"})      # a stated name never overrides an exact English match
    assert R["create_promise"]["amount"] == "amount"
    # ... but it does replace a weak (synonym/description/fallback) mapping or fill a gap
    tools2 = _tools(ROOT / "tests/fixtures/external/orrery-seven/openapi.json")
    R2 = CO.request_slots(tools2, {"create_promise.amount": "fecha", "create_promise.date": "importe"})
    assert R2["create_promise"]["amount"] == "fecha" and R2["create_promise"]["date"] == "importe"


def test_compiled_body_carries_alias(tmp_path):
    import compile as C
    ir = P.PolicyIR.load(str(ROOT / "tests/fixtures/brief_a.policy.json"))
    spec = json.load(open(ROOT / "tools/openapi.json"))
    body = spec["paths"]["/create_promise"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    body["properties"]["sum"] = body["properties"].pop("amount")       # properties say `sum`, required still says `amount`
    (tmp_path / "api.json").write_text(json.dumps(spec))
    tools = _tools(tmp_path / "api.json")
    wf = C.compile_workflow(ir, tools)
    nodes = wf["nodes"]
    node = nodes["create_promise"] if isinstance(nodes, dict) else next(n for n in nodes if n["name"] == "create_promise")
    text = json.dumps(node)
    assert '"amount"' in text and '"sum"' in text
    assert "['sum', 'amount']" in node["pre_actions"][0]["pre_process_code"]


def test_allof_enums_intersect_oneof_unite():
    sch = {"type": "object", "properties": {"x": {"type": "string", "enum": ["a", "b", "c"]}},
           "allOf": [{"properties": {"x": {"enum": ["b", "c", "d"]}}}]}
    assert CO._flatten_composition(sch)["properties"]["x"]["enum"] == ["b", "c"]
    sch = {"type": "object", "properties": {"x": {"type": "string", "enum": ["a"]}},
           "oneOf": [{"properties": {"x": {"enum": ["b"]}}}]}
    assert CO._flatten_composition(sch)["properties"]["x"]["enum"] == ["a", "b"]


def test_api_fields_round_trip():
    ir = P.PolicyIR.from_dict({"api_fields": {"get_account.past_due": "outst"}})
    assert ir.api_fields == {"get_account.past_due": "outst"}
    assert P.unknown_special_cases(ir) == []


def test_spanish_names_map_by_synonym():
    tools = _tools(ROOT / "tests/fixtures/external/orrery-seven/openapi.json")
    R = CO.request_slots(tools)
    assert R["verify_identity"] == {"customer_id": "cust_ref", "field": "pregunta", "answer": "respuesta"}
    assert R["create_promise"] == {"customer_id": "cust_ref", "product_id": "contrato", "amount": "importe", "date": "fecha"}
    assert R["close_call"] == {"customer_id": "cust_ref", "outcome": "resultado", "reason": "motivo"}
    S = CO.response_slots(tools)
    assert S["account"]["list"] == "cartera" and S["account"]["id"] == "contrato" and S["account"]["type"] == "clase"
    assert S["verify"] == {"ok": "success", "verified": "answer_ok", "all_verified": "identity_ok", "remaining": "tries_left", "hint": "__none__"}


def test_camel_case_and_description_and_type_fallbacks():
    assert CO._norm("pastDueAmount") == "past_due_amount" and CO._norm("Días") == "dias"
    assert CO._hit("days", "dl_days") and not CO._hit("days", "holidays") and CO._hit("_id", "facility_id") and not CO._hit("_id", "identity")
    # description round: nonsense names, meaningful descriptions
    props = {"f1": {"type": "string", "description": "The promised payment amount"}, "f2": {"type": "string", "description": "Promised payment date"}}
    assert CO._pick(props, "amount", "sum") == "f1" and CO._pick(props, "date", "day") == "f2"
    # type/position fallback: no names, no descriptions
    m = {"customer_id": "c"}
    CO._request_fallback("create_promise", {"c": {"type": "string"}, "x1": {"type": "string"}, "x2": {"type": "number"}, "x3": {"type": "string", "format": "date"}}, m)
    assert m == {"customer_id": "c", "amount": "x2", "date": "x3", "product_id": "x1"}


def test_customer_anchor_from_get_account():
    import json
    spec = json.load(open(ROOT / "tools/openapi.json"))
    for path, ops in spec["paths"].items():
        body = ops["post"]["requestBody"]["content"]["application/json"]["schema"]
        body["properties"]["zqx"] = body["properties"].pop("customer_id")
        body["required"] = ["zqx" if r == "customer_id" else r for r in body.get("required", [])]
    import tempfile, pathlib as pl
    d = pl.Path(tempfile.mkdtemp()); (d / "api.json").write_text(json.dumps(spec))
    R = CO.request_slots(_tools(d / "api.json"))
    assert all(m["customer_id"] == "zqx" for m in R.values())


def test_nested_product_list_and_cross_tool_anchors():
    S = CO.response_slots(_tools(ROOT / "tests/fixtures/external/r2-api-nested-products/openapi.json"))
    assert S["account"]["list"] == "payload.products" and S["account"]["past_due"] == "past_due"
    tools = _tools(ROOT / "tests/fixtures/external/selvi-turkish-fields/openapi.json")   # Turkish names, no descriptions, shuffled order
    R = CO.request_slots(tools)
    assert R["create_promise"] == {"customer_id": "musteri_no", "product_id": "sozlesme", "amount": "tutar", "date": "tarih"}
    assert R["add_note"]["product_id"] == "sozlesme" and R["add_note"]["reason"] == "neden" and R["add_note"]["text"] == "metin"
    assert R["close_call"]["reason"] == "neden" and R["close_call"]["outcome"] == "sonuc"
    assert R["schedule_callback"] == {"customer_id": "musteri_no", "date": "tarih", "time": "saat"}
    V = CO.response_slots(tools)["verify"]
    assert V["ok"] == "basarili"
