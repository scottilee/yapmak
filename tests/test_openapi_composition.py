"""OpenAPI compositions (oneOf refinements per product type / per outcome) are flattened, not rejected (v23, external packages)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import compile as C  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_one_of_refinements_are_flattened():
    tools = C.parse_openapi(str(ROOT / "tests/fixtures/external/codex-aster-quay/openapi.json"))
    cc = tools["close_call"]
    assert set(cc.body_props) == {"customer_id", "outcome", "reason"} and sorted(cc.required) == ["customer_id", "outcome"]
    assert "aq-promised" in cc.body_props["outcome"]["enum"] and "aq-r-care" in cc.body_props["reason"]["enum"]
    items = tools["get_account"].response_props["facilities"]["items"]["properties"]
    assert {"facility_ref", "facility_kind", "arrears_total", "days_overdue", "flex_minimum", "term_instalment"} <= set(items)
    slots = C.response_slots(tools)
    assert slots["account"]["id"] == "facility_ref" and slots["account"]["past_due"] == "arrears_total" and slots["account"]["days_late"] == "days_overdue"
    R = C.request_slots(tools)
    assert R["close_call"]["outcome"] == "outcome" and R["close_call"]["reason"] == "reason"


def test_second_package_parses_and_maps():
    tools = C.parse_openapi(str(ROOT / "tests/fixtures/external/codex-bracken-thread/openapi.json"))
    assert C.response_slots(tools)["account"]["list"] and C.request_slots(tools)["create_promise"]["amount"]


def test_all_of_merges_required():
    from compiler_openapi import _flatten_composition
    s = _flatten_composition({"allOf": [{"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
                                        {"properties": {"b": {"type": "number"}}, "required": ["b"]}]})
    assert set(s["properties"]) == {"a", "b"} and sorted(s["required"]) == ["a", "b"] and s["type"] == "object"


def test_verify_success_flag_named_accepted_is_mapped():
    for pkg in ("v24-sable-percent", "v24-tamarisk-thread"):
        tools = C.parse_openapi(str(ROOT / "tests/fixtures/external" / pkg / "openapi.json"))
        slots = C.response_slots(tools)
        assert slots["verify"]["ok"] == "accepted" and slots["verify"]["verified"] == "answer_matches" and slots["verify"]["remaining"] == "security_remaining"
        assert C.request_slots(tools)["close_call"]["outcome"]
