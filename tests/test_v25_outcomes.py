"""v25: a policy without a paid or transfer outcome (documents that have none) validates and closes correctly."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import policy as P  # noqa: E402
import compiler_openapi as CO  # noqa: E402
import compile as C  # noqa: E402


def _ir_without_paid_and_transfer():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["outcomes"]["paid_outcome"] = ""
    d["outcomes"]["transfer_outcome"] = ""
    d["outcomes"]["table"] = [r for r in d["outcomes"]["table"] if r["outcome"] not in ("paid", "transferred")]
    d["special_cases"] = [sc for sc in d["special_cases"] if sc["name"] in ("dispute", "refuse_to_talk")]
    return d


def test_validates_without_paid_or_transfer_outcome():
    tools = CO.parse_openapi(str(ROOT / "tools/openapi.json"))
    ir = P.PolicyIR.from_dict(_ir_without_paid_and_transfer())
    assert not [e for e in P.validate(ir, CO.tool_enums(tools)) if "paid_outcome" in e or "transfer_outcome" in e]
    wf = C.compile_workflow(ir, tools)
    assert wf["nodes"]


def test_still_required_when_a_path_needs_them():
    tools = CO.parse_openapi(str(ROOT / "tools/openapi.json"))
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["outcomes"]["paid_outcome"] = ""
    d["outcomes"]["transfer_outcome"] = ""
    for sc in d["special_cases"]:
        sc["action"].pop("outcome", None)
    errs = P.validate(P.PolicyIR.from_dict(d), CO.tool_enums(tools))
    assert any("paid_outcome is empty" in e for e in errs) and any("transfer_outcome is empty" in e for e in errs)
