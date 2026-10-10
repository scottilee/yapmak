"""Policy extraction: brief document(s) + OpenAPI -> structural policy IR (policy.py), via the Claude Agent SDK.

Three bounded model passes (plan §3.1):
  1. extract   - read the source documents and the tool API, write out/<slot>.policy.json
  2. audit     - a fresh context re-reads the sources and the JSON, reports omissions/conflicts and writes a corrected JSON
  3. repair    - only if policy.validate() still reports problems: one more pass with the error list

Nothing in this file knows any bank's values. Model calls are logged to the trace (model, purpose, duration).
Needs a Claude login or ANTHROPIC_API_KEY, like the kit's example builder.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time

import policy as P

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")

SCHEMA_GUIDE = """
The JSON must deserialize with `policy.PolicyIR.from_dict` (read policy.py for every field and its meaning). Rules:
- Every value comes from the source documents or the tool API file. Never invent a holiday, a threshold, an outcome name, a queue or a phrase.
  If the documents do not say, leave the field at its default and add an entry to `unresolved` ({"topic", "text", "doc"}).
- `identity.requirements`: the security questions in the order the documents ask them. `field` must be a value of the `field` enum of
  verify_identity in the tool API. `answer_format`: date | digits | year | text. For dates, `numeric_date_order` is how a date said only
  as numbers is read (dmy or mdy). `hint_field`/`hint_reply` when the API returns a hint for a recoverable format mistake.
- Outcomes: `failed_outcome`, `declined_outcome`, `unclear_holder_outcome`, callback outcomes, `wrong_number_outcome`, `deceased_outcome`
  are [outcome, reason] pairs; outcome must be a value of the close_call `outcome` enum, reason a value the documents list for it ("" if none).
- `bands`: one per days-late band. `deadline` uses the DSL: {"kind":"nth_business_day","n":N} | {"kind":"calendar_days","n":N,"adjustment":"none|following|preceding"}
  | {"kind":"fixed_date","date":"YYYY-MM-DD","adjustment":...} | {"kind":"end_of_month","basis":"calendar|business","adjustment":...}.
  `attempts`: the persuasion attempts in order, each {"amount":"full|floor","date":"last_business_day_this_week_or_next|deadline|today|next_business_day","floor_if_full_refused":bool}.
- `amounts.floors`: product type (a value of the product `type` enum in get_account) -> the response property that holds the lowest acceptable amount.
- `special_cases`: one per situation the documents handle (already paid, dispute, hardship, restructuring, human request, scam question,
  refusal to talk, ...). `trigger` is a plain-language description of what the customer says. `action` is {"type":"close","outcome":..,"reason":..}
  or {"type":"transfer","queue":..,"outcome":..,"reason":..} or {"type":"note","reason":..} or {"type":"continue"}.
  Use `offer_transfer_queue` + `offer_outcome` when the policy offers a transfer first and `action` applies if the customer declines.
  `before_persuasion`, `ask_once_first`, `takes_promise`, `ends_call` as the documents say. Keep the names already_paid, dispute, hardship,
  restructuring, human, scam, refuse_to_talk for those situations when they exist, so the compiler recognises them.
- `outcomes.table`: every outcome with its allowed reasons exactly as the documents list them. Also fill promise_outcome, paid_outcome,
  transfer_outcome, no_promise_outcome, service_error_reason, refused_reason and the precedence booleans.
- `notes`: enabled only if the documents use add_note; `reasons` are the add_note `reason` values the documents allow.
- `multi_product.max_products`: how many products a customer can have according to the documents (1 if only one is ever mentioned).
- `phrases`: mandatory sentences verbatim (opening sentence, the question that confirms who is on the line using {{title}} and {{last_name}},
  the sentence after a recorded promise, the already-paid sentence, the robot reply, the scam reply, the cannot-answer sentence, the reply when
  a customer wants to change a recorded promise), the words that must not be said before verification, and `product_naming`: product type ->
  how to name it in words (use {card_last4} where the documents say to name the card's last digits).
- `promise_write.retry_on_failure`: how many extra attempts after a failed create_promise (0 if the documents say none).
- Later documents in the input list override earlier ones only where they say so; a memo that changes a policy wins over the policy it changes.
  Record each value's origin in its `source` {"doc","text"}.
- No null values anywhere: use "" or [] or omit the key.
"""


PASS_TIMEOUT_S = int(os.environ.get("EXTRACT_PASS_TIMEOUT_S", "420"))   # one model pass may not exceed this (plan §7 budget)


async def _query(prompt: str, purpose: str, trace, max_turns=40) -> dict:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolUseBlock, query

    options = ClaudeAgentOptions(
        cwd=ROOT, model=MODEL, setting_sources=[], allowed_tools=["Read", "Write", "Glob", "Grep"],
        permission_mode="dontAsk", max_turns=max_turns,
    )
    t0 = time.time()
    text, tools, result = [], [], None
    timed_out = False

    async def consume():
        nonlocal result
        async for m in query(prompt=prompt, options=options):
            if isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, TextBlock):
                        text.append(b.text)
                    elif isinstance(b, ToolUseBlock):
                        tools.append(b.name + ":" + str(b.input.get("file_path", ""))[-60:])
            elif isinstance(m, ResultMessage):
                result = m
    try:
        await asyncio.wait_for(consume(), timeout=PASS_TIMEOUT_S)
    except asyncio.TimeoutError:
        timed_out = True
    rec = {"model": MODEL, "purpose": purpose, "duration_ms": int((time.time() - t0) * 1000), "timed_out": timed_out,
           "turns": getattr(result, "num_turns", None), "cost_usd": getattr(result, "total_cost_usd", None), "tools": tools[:40],
           "text_tail": " ".join(text)[-600:]}
    if trace:
        trace.event("model_call", **rec)
    return rec


def _sources_text(brief_paths):
    return "\n".join(f"- {p}" for p in brief_paths)


def extract(brief_paths: list[str], openapi_path: str, slot: str, trace=None) -> tuple[P.PolicyIR, dict]:
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    ir_path = out / f"{slot}.policy.json"
    audit_path = out / f"{slot}.audit.json"
    if ir_path.exists():
        ir_path.unlink()
    import compile as C
    tools = C.parse_openapi(openapi_path)
    enums = C.tool_enums(tools)

    prompt1 = f"""You are compiling a bank's phone-collections policy into a structured JSON policy for a workflow compiler.
Read ALL of these source documents completely, in order:
{_sources_text(brief_paths)}
Then read the tool API file {openapi_path} (the enums there are the only allowed values for outcomes, reasons, queues, note reasons,
identity fields and product types). Then read policy.py for the exact JSON schema.
{SCHEMA_GUIDE}
Write the JSON to {ir_path.relative_to(ROOT)} with the Write tool. Write nothing else. Do not run code."""
    asyncio.run(_query(prompt1, "policy_extraction", trace))
    if not ir_path.exists():
        raise RuntimeError("extraction produced no policy file")

    prompt2 = f"""You are the independent auditor of a policy extraction. Do NOT trust the extraction: re-read the source documents yourself.
Source documents, in order:
{_sources_text(brief_paths)}
Tool API file: {openapi_path}. Schema: policy.py. Extracted policy: {ir_path.relative_to(ROOT)}.
{SCHEMA_GUIDE}
Task: go through the source documents rule by rule (every numbered rule, every table row, every sentence that constrains the agent) and check
that each is represented in the JSON (as a value, a special case, a phrase, a band, an outcome row, or an `unresolved` entry). Check that every
value in the JSON is literally supported by the documents and that enum values exist in the tool API. Check document precedence where several
documents conflict.
Then: (1) write the corrected JSON back to {ir_path.relative_to(ROOT)} (full file); (2) write {audit_path.relative_to(ROOT)} as JSON:
{{"covered": [{{"rule": "<short quote or number>", "where": "<json path>"}}], "fixed": ["<what you changed and why>"], "unresolved": ["<what the documents do not settle>"]}}.
Do not run code."""
    asyncio.run(_query(prompt2, "policy_audit", trace))

    ir = P.PolicyIR.load(str(ir_path))
    problems = P.validate(ir, enums)
    if problems:
        prompt3 = f"""The policy JSON at {ir_path.relative_to(ROOT)} fails validation. Fix exactly these problems by re-reading the source documents
({_sources_text(brief_paths)}) and the tool API file {openapi_path}; see policy.py for the schema and {SCHEMA_GUIDE}
Problems:
""" + "\n".join("- " + p for p in problems) + f"\nWrite the corrected full JSON back to {ir_path.relative_to(ROOT)}. Do not run code."
        asyncio.run(_query(prompt3, "policy_repair", trace, max_turns=20))
        ir = P.PolicyIR.load(str(ir_path))
        problems = P.validate(ir, enums)
        if problems:
            raise RuntimeError("policy still invalid after repair: " + "; ".join(problems))
    audit = json.load(open(audit_path)) if audit_path.exists() else {}
    if trace:
        trace.event("policy_compiled", artifact=str(ir_path.relative_to(ROOT)), bands=len(ir.bands), identity_fields=[r.field for r in ir.identity.requirements],
                    special_cases=[s.name for s in ir.special_cases], unresolved=ir.unresolved, audit_fixed=audit.get("fixed", []), audit_unresolved=audit.get("unresolved", []))
    return ir, audit


if __name__ == "__main__":
    import sys
    from trace import Trace
    briefs, openapi, slot = sys.argv[1].split(","), sys.argv[2], sys.argv[3]
    tr = Trace(ROOT / "traces" / f"{slot}.extract.jsonl")
    ir, audit = extract(briefs, openapi, slot, tr)
    print(json.dumps({"bands": [b.name for b in ir.bands], "identity": [r.field for r in ir.identity.requirements],
                      "special_cases": [s.name for s in ir.special_cases], "unresolved": ir.unresolved, "audit_fixed": audit.get("fixed")}, indent=1))
