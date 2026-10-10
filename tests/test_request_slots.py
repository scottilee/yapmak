"""Request field names come from the supplied OpenAPI document, never from the practice kit (plan §3.2)."""
import copy
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import compile as C  # noqa: E402
import policy as P  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
RENAMES = {  # tool -> {old request field: new name}
    "verify_identity": {"field": "check", "answer": "value"},
    "create_promise": {"product_id": "facility_ref", "amount": "promised_amount", "date": "promise_date"},
    "add_note": {"product_id": "facility_ref", "reason": "note_code"},
    "schedule_callback": {"date": "callback_day", "time": "callback_hour"},
    "transfer_to_agent": {"queue": "team"},
    "close_call": {"outcome": "disposition_code", "reason": "sub_code"},
}


def _mutated_openapi(tmp_path, renames=RENAMES, drop_customer=False):
    spec = json.load(open(ROOT / "tools" / "openapi.json"))
    for path, ops in spec["paths"].items():
        name = path.strip("/")
        for op in ops.values():
            schema = op["requestBody"]["content"]["application/json"]["schema"]
            props = schema["properties"]
            for old, new in renames.get(name, {}).items():
                props[new] = props.pop(old)
                schema["required"] = [new if r == old else r for r in schema.get("required", [])]
            if drop_customer:
                props.pop("customer_id", None)
                schema["required"] = [r for r in schema.get("required", []) if r != "customer_id"]
    out = tmp_path / "openapi.json"
    out.write_text(json.dumps(spec))
    return str(out)


def _bodies(wf):
    return {k: n["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]
            for k, n in wf["nodes"].items() if n["node_type"] == "api_request"}


def test_practice_api_maps_to_itself():
    tools = C.parse_openapi(str(ROOT / "tools" / "openapi.json"))
    R = C.request_slots(tools)
    assert R["close_call"] == {"customer_id": "customer_id", "outcome": "outcome", "reason": "reason"}
    assert R["create_promise"]["amount"] == "amount" and R["verify_identity"]["answer"] == "answer"


def test_renamed_request_fields_are_discovered(tmp_path):
    tools = C.parse_openapi(_mutated_openapi(tmp_path))
    ir = P.PolicyIR.load(str(ROOT / "tests/fixtures/brief_a.policy.json"))
    assert not P.validate(ir, C.tool_enums(tools))          # enums are keyed by meaning, so the IR still validates
    wf = C.compile_workflow(ir, tools)
    assert not C.static_check(wf, tools)
    b = _bodies(wf)
    assert set(b["close_reason"]) == {"customer_id", "disposition_code", "sub_code"}
    assert set(b["close_noreason"]) == {"customer_id", "disposition_code"}
    assert set(b["create_promise"]) == {"customer_id", "facility_ref", "promised_amount", "promise_date"}
    assert b["create_promise"]["promised_amount"]["default"] == "{{w_amount}}"
    assert b["verify_0"]["check"]["default"] == "date_of_birth" and b["verify_0"]["value"]["default"] == "{{id_answer}}"
    assert set(b["schedule_callback"]) == {"customer_id", "callback_day", "callback_hour"}
    assert set(b["transfer"]) == {"customer_id", "team"}
    assert "promised_amount" in wf["nodes"]["create_promise"]["pre_actions"][0]["pre_process_code"]


def test_schema_without_customer_id_omits_it(tmp_path):
    tools = C.parse_openapi(_mutated_openapi(tmp_path, renames={}, drop_customer=True))
    ir = P.PolicyIR.load(str(ROOT / "tests/fixtures/brief_a.policy.json"))
    wf = C.compile_workflow(ir, tools)
    assert "customer_id" not in _bodies(wf)["create_promise"]
    assert not C.static_check(wf, tools)


def test_unmappable_required_argument_stops_the_build(tmp_path):
    tools = C.parse_openapi(_mutated_openapi(tmp_path, renames={"close_call": {"outcome": "zz_final"}}))
    with pytest.raises(SystemExit, match="close_call.outcome"):
        C.request_slots(tools)
