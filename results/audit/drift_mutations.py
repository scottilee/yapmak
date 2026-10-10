"""Auditor repro: schema-drift mutations of tools/openapi.json + matching IR edits, compiled offline.
Never calls Freya. Usage (repo root): .venv/bin/python results/audit/drift_mutations.py
"""
import copy, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TMP = pathlib.Path(__file__).resolve().parent / "drift-out"
TMP.mkdir(exist_ok=True)
PY = str(ROOT / ".venv" / "bin" / "python")
oa0 = json.load(open(ROOT / "tools/openapi.json"))
ir0 = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
ab0 = json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json"))


def resp(spec, tool):
    return spec["paths"][tool]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]


def comp(tag, openapi, policy, ab=None):
    (TMP / f"oa_{tag}.json").write_text(json.dumps(openapi))
    (TMP / f"ir_{tag}.json").write_text(json.dumps(policy))
    paths = str(TMP / f"ir_{tag}.json") + (f"+{TMP}/ir_{tag}_ab.json" if ab else "")
    if ab:
        (TMP / f"ir_{tag}_ab.json").write_text(json.dumps(ab))
    p = subprocess.run([PY, "compile.py", paths, str(TMP / f"oa_{tag}.json"), str(TMP / f"wf_{tag}.json")],
                       cwd=ROOT, capture_output=True, text=True)
    print(f"== {tag}: exit={p.returncode} :: {(p.stdout + p.stderr).replace(chr(10), ' ')[:150]}")
    return p.returncode


# X1: verify response ok->ack, verified->passed -> mapping silently keeps data.ok/data.verified (never set)
m = copy.deepcopy(oa0); v = resp(m, "/verify_identity"); v["ack"] = v.pop("ok"); v["passed"] = v.pop("verified")
comp("x1_verify_renames", m, copy.deepcopy(ir0))

# X2: create_promise ok->executed -> every write looks failed; agent retries then closes service_error
#     while the bank actually recorded the promise (see offline_probes.py header note; run wf against a
#     mock returning 'executed' to reproduce the double-record + wrong outcome).
m = copy.deepcopy(oa0); resp(m, "/create_promise")["executed"] = resp(m, "/create_promise").pop("ok")
comp("x2_write_ok_rename", m, copy.deepcopy(ir0))

# X3: add_note reason dispute->claimed_dispute, IR updated consistently -> compile ok but the engine's
#     disposition literal 'dispute' is not in notes.reasons -> add_note silently skipped for that product.
m = copy.deepcopy(oa0)
m["paths"]["/add_note"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["reason"]["enum"][2] = "claimed_dispute"
ir3 = copy.deepcopy(ir0)
for row in ir3["outcomes"]["table"]:
    if "dispute" in row["reasons"]:
        row["reasons"][row["reasons"].index("dispute")] = "claimed_dispute"
[s for s in ir3["special_cases"] if s["name"] == "dispute"][0]["action"]["reason"] = "claimed_dispute"
ab3 = copy.deepcopy(ab0)
ab3["notes"]["reasons"] = ["claimed_dispute" if x == "dispute" else x for x in ab3["notes"]["reasons"]]
ab3["special_cases_override"]["dispute"]["action"]["reason"] = "claimed_dispute"
comp("x3_note_reason_rename", m, ir3, ab=ab3)

# X4: days_late -> overdue_since (no needle match) -> silent stale 'days_late' -> 0 -> wrong band for every product
m = copy.deepcopy(oa0)
items = resp(m, "/get_account")["products"]["items"]["properties"]
items["overdue_since"] = items.pop("days_late")
comp("x4_dayslate_rename", m, copy.deepcopy(ir0))

# M3: outcome enum changed WITHOUT IR update -> fails loudly (policy invalid) -- GOOD
m = copy.deepcopy(oa0)
m["paths"]["/close_call"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["outcome"]["enum"][0] = "promised"
comp("m3_outcome_enum_no_ir", m, copy.deepcopy(ir0))

# M4: new required field on create_promise -> static check fails loudly -- GOOD
m = copy.deepcopy(oa0)
sch = m["paths"]["/create_promise"]["post"]["requestBody"]["content"]["application/json"]["schema"]
sch["properties"]["channel"] = {"type": "string", "enum": ["sms", "email"]}
sch["required"].append("channel")
comp("m4_required_field", m, copy.deepcopy(ir0))

# M1: wrong_answers_left -> attempts_left -> adapts (needle 'left'/'attempts') -- GOOD
m = copy.deepcopy(oa0)
resp(m, "/verify_identity")["attempts_left"] = resp(m, "/verify_identity").pop("wrong_answers_left")
comp("m1_remaining_rename", m, copy.deepcopy(ir0))


# R1: request fields renamed on every write tool (outcome->disposition_code, amount->promised_amount, date->promise_date,
#     product_id->facility_ref, queue->team, field/answer->check/value) -> must compile, bodies must carry the new names
def req(spec, tool):
    return spec["paths"][tool]["post"]["requestBody"]["content"]["application/json"]["schema"]

RENAMES = {"/verify_identity": {"field": "check", "answer": "value"}, "/create_promise": {"product_id": "facility_ref", "amount": "promised_amount", "date": "promise_date"},
           "/add_note": {"product_id": "facility_ref", "reason": "note_code"}, "/schedule_callback": {"date": "callback_day", "time": "callback_hour"},
           "/transfer_to_agent": {"queue": "team"}, "/close_call": {"outcome": "disposition_code", "reason": "sub_code"}}
m = copy.deepcopy(oa0)
for tool, ren in RENAMES.items():
    s = req(m, tool)
    for old, new in ren.items():
        s["properties"][new] = s["properties"].pop(old)
        s["required"] = [new if r == old else r for r in s.get("required", [])]
rc = comp("r1_request_renames", m, copy.deepcopy(ir0), copy.deepcopy(ab0))
if rc == 0:
    wf = json.load(open(TMP / "wf_r1_request_renames.json"))
    bodies = {k: sorted(n["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]) for k, n in wf["nodes"].items() if n["node_type"] == "api_request"}
    ok = bodies["create_promise"] == ["customer_id", "facility_ref", "promise_date", "promised_amount"] and bodies["close_reason"] == ["customer_id", "disposition_code", "sub_code"] and bodies["transfer"] == ["customer_id", "team"]
    print(f"   bodies use the renamed fields: {ok}")

# R2: a required request field with no recognisable name (close_call outcome -> zz_final) -> must stop the build, naming the tool.argument
m = copy.deepcopy(oa0); s = req(m, "/close_call"); s["properties"]["zz_final"] = s["properties"].pop("outcome"); s["required"] = ["zz_final" if r == "outcome" else r for r in s["required"]]
comp("r2_request_unmappable", m, copy.deepcopy(ir0))
