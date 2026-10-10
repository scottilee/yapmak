"""Structural policy IR: the small, typed part of a brief that the workflow compiler parameterizes.

Two layers make up a compiled policy (plan §3.1):
  1. this structural IR (numbers, calendars, enums, rule shapes) with a source span per value,
  2. LLM-authored prompt text per template stage (see `PromptSet`).

Nothing in this module knows any bank's values. Practice fixtures live in tests/fixtures/*.policy.json.

The IR is plain JSON-serializable dataclasses so that an extractor can emit it, the auditor can diff it
against the source text, and the compiler can embed its values into code nodes.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------------------------
# Deadline-rule DSL. Anything the compiler cannot express goes to PolicyIR.unresolved.
#   {"kind": "nth_business_day", "n": 12}      the n-th business day after today
#   {"kind": "calendar_days", "n": 14}         today + n calendar days; explicit adjustment required
#   {"kind": "fixed_date", "date": "YYYY-MM-DD"}
#   {"kind": "end_of_month"}                   explicit basis=calendar|business and adjustment required
DEADLINE_KINDS = ("nth_business_day", "calendar_days", "fixed_date", "end_of_month")

# Date sources an attempt may propose.
ATTEMPT_DATE_SOURCES = ("last_business_day_this_week_or_next", "deadline", "today", "next_business_day")
ATTEMPT_AMOUNT_SOURCES = ("full", "floor")

ANSWER_FORMATS = ("date", "digits", "year", "text")


@dataclass
class Span:
    """Where a value came from. `doc` is the source file, `text` the quoted sentence or cell."""
    doc: str = ""
    text: str = ""


@dataclass
class IdentityRequirement:
    field: str                      # value of the OpenAPI `field` enum, e.g. date_of_birth
    ask_text: str                   # how to ask, in the agent's words
    answer_format: str = "text"     # one of ANSWER_FORMATS; drives extraction validation + normalization
    digits: int = 0                 # for `digits`: exact length
    numeric_date_order: str = "dmy" # for `date` when the customer says only numbers
    hint_field: str = ""            # response property carrying a format hint (e.g. `hint`)
    hint_reply: str = ""            # what to say when the hint fires (does not count as wrong)
    source: Span = field(default_factory=Span)


@dataclass
class IdentityPolicy:
    requirements: list[IdentityRequirement] = field(default_factory=list)
    wrong_answer_limit: int = 3             # global across questions
    wrong_count_source: str = "api"         # "api" (use remaining-attempts slot) or "code"
    remaining_slot: str = ""                # response property with wrong answers left, if any
    holder_confirmation_asks: int = 2       # how many times to ask "am I speaking with ..."
    decline_explain_once: bool = True       # explain the purpose once, then close on second decline
    asking_purpose_counts_as_decline: bool = True
    failed_outcome: tuple[str, str] = ("", "")     # (outcome, reason) after too many wrong answers
    declined_outcome: tuple[str, str] = ("", "")
    unclear_holder_outcome: tuple[str, str] = ("", "")
    failed_instruction: str = ""            # what to tell the customer after a failed check
    source: Span = field(default_factory=Span)


@dataclass
class CallbackPolicy:
    enabled: bool = True
    days: str = "today_or_next_business_day"   # today_or_next_business_day | next_business_day | today
    start: str = "10:00"
    end: str = "19:00"
    must_be_after_now: bool = True
    retry_once: bool = True
    scheduled_outcome: tuple[str, str] = ("", "")
    no_callback_outcome: tuple[str, str] = ("", "")
    source: Span = field(default_factory=Span)


@dataclass
class ThirdPartyPolicy:
    callback: CallbackPolicy = field(default_factory=CallbackPolicy)
    wrong_number_outcome: tuple[str, str] = ("", "")
    deceased_outcome: tuple[str, str] = ("", "")
    deceased_sentence: str = ""
    source: Span = field(default_factory=Span)


@dataclass
class Calendar:
    holidays: list[str] = field(default_factory=list)   # ISO dates
    business_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Monday=0
    next_weekday_means_following_week: bool = True      # "next Friday" on a Friday = Friday of next week
    missing_date_parts: str = "unresolved"  # next_occurrence only when explicitly selected
    source: Span = field(default_factory=Span)


@dataclass
class Attempt:
    amount: str = "full"                                  # ATTEMPT_AMOUNT_SOURCES
    date: str = "last_business_day_this_week_or_next"     # ATTEMPT_DATE_SOURCES
    floor_if_full_refused: bool = True                    # attempt names the floor if the full amount was already refused


@dataclass
class Band:
    name: str
    days_late_min: int
    days_late_max: int
    deadline: dict[str, Any]                 # DeadlineRule
    attempts: list[Attempt] = field(default_factory=list)
    source: Span = field(default_factory=Span)


@dataclass
class AmountPolicy:
    floors: dict[str, str] = field(default_factory=dict)   # product type -> response property with the floor
    full_first: bool = True
    never_ask_how_much: bool = True
    floor_offered_once: bool = True
    floor_wording: str = ""                                 # e.g. "the rest stays overdue"
    accept_between_floor_and_full: bool = True
    source: Span = field(default_factory=Span)


@dataclass
class DatePolicy:
    promise_today_allowed: bool = True
    weekend_or_holiday_roll_forward: bool = True
    vague_ask_once_then_deadline: bool = True
    after_deadline_offer_deadline: bool = True
    source: Span = field(default_factory=Span)


@dataclass
class SpecialCase:
    """A thing the customer says, and what the policy does about it."""
    name: str                                # already_paid | dispute | hardship | restructuring | human | scam | refuse_to_talk | ...
    trigger: str                             # natural-language description for extraction/routing
    action: dict[str, Any]                   # {"type": "close", "outcome": .., "reason": ..} |
                                             # {"type": "transfer", "queue": .., "outcome": .., "reason": ..} |
                                             # {"type": "note", "reason": ..} | {"type": "continue"}
    say: str = ""                            # mandatory sentence, if any
    offer_transfer_queue: str = ""           # hardship-style: offer a transfer first; action applies if declined
    offer_outcome: tuple[str, str] = ("", "")
    before_persuasion: bool = False          # this rule wins over persuasion attempts
    ask_once_first: bool = False             # "ask once whether you can help", then act
    takes_promise: bool = False              # the customer may still name a date/amount -> record it
    ends_call: bool = True                   # single-product: close; multi-product: note and continue
    source: Span = field(default_factory=Span)


@dataclass
class OutcomeRow:
    outcome: str
    reasons: list[str] = field(default_factory=list)   # empty = no reason
    when: str = ""


@dataclass
class OutcomePolicy:
    table: list[OutcomeRow] = field(default_factory=list)
    promise_outcome: str = ""                 # outcome when at least one promise was recorded
    paid_outcome: str = ""
    transfer_outcome: str = ""
    transfer_overrides_promise: bool = True
    no_promise_outcome: str = ""
    all_paid_closes_as_paid: bool = True      # multi-product: all noted paid -> paid
    no_promise_reason_from_first_non_paid_note: bool = True
    service_error_reason: str = ""
    refused_reason: str = ""
    goodbye_before_close: bool = True
    source: Span = field(default_factory=Span)


@dataclass
class NotesPolicy:
    enabled: bool = False                     # Brief A never uses add_note
    reasons: list[str] = field(default_factory=list)
    note_each_unpromised_product: bool = True
    none_on_transfer: bool = True
    source: Span = field(default_factory=Span)


@dataclass
class MultiProductPolicy:
    max_products: int = 3
    state_all_before_asking: bool = True
    ask_all_today_once: bool = True
    per_product_attempts: bool = True
    common_date_clamped_per_product: bool = True
    one_confirmation_for_batch: bool = True
    recorded_promises_survive_transfer: bool = True
    source: Span = field(default_factory=Span)


@dataclass
class Phrases:
    opening: str = ""                          # first sentence, verbatim where the brief dictates
    opening_verbatim: bool = False             # True when the documents require the opening to be said word for word
    holder_question: str = ""                  # "Am I speaking with {{title}} {{last_name}}?"
    debt_intro: str = ""                       # sentence introducing the reason for the call after verification, if dictated
    today_question: str = ""                   # the first ask, e.g. "Can you make this payment today?"
    all_today_question: str = ""               # the first ask with several products
    robot_reply: str = ""
    scam_reply: str = ""
    prohibited_before_verification: list[str] = field(default_factory=list)
    after_promise_sentence: str = ""           # said only after a successful write
    already_paid_sentence: str = ""
    cannot_answer_sentence: str = ""
    recorded_promise_change_reply: str = ""    # "you can change it in the mobile app"
    product_naming: dict[str, str] = field(default_factory=dict)   # type -> spoken form template
    source: Span = field(default_factory=Span)


@dataclass
class PromiseWritePolicy:
    retry_on_failure: int = 1                  # extra attempts after the first failure
    one_promise_per_product: bool = True
    confirm_phrase: str = "Do you confirm?"
    source: Span = field(default_factory=Span)


@dataclass
class PolicyIR:
    source_docs: list[str] = field(default_factory=list)
    bank_name: str = ""
    identity: IdentityPolicy = field(default_factory=IdentityPolicy)
    third_party: ThirdPartyPolicy = field(default_factory=ThirdPartyPolicy)
    calendar: Calendar = field(default_factory=Calendar)
    bands: list[Band] = field(default_factory=list)
    amounts: AmountPolicy = field(default_factory=AmountPolicy)
    dates: DatePolicy = field(default_factory=DatePolicy)
    special_cases: list[SpecialCase] = field(default_factory=list)
    outcomes: OutcomePolicy = field(default_factory=OutcomePolicy)
    notes: NotesPolicy = field(default_factory=NotesPolicy)
    multi_product: MultiProductPolicy = field(default_factory=MultiProductPolicy)
    phrases: Phrases = field(default_factory=Phrases)
    promise_write: PromiseWritePolicy = field(default_factory=PromiseWritePolicy)
    unresolved: list[dict[str, str]] = field(default_factory=list)   # {"topic", "text", "doc"}

    # -- serialization -------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=1)

    @classmethod
    def from_dict(cls, d: dict) -> "PolicyIR":
        return _build(cls, d)

    @classmethod
    def load(cls, path: str) -> "PolicyIR":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def load_merged(cls, paths: list[str]) -> "PolicyIR":
        """First path is a full IR; later paths are overlays (deep-merged; `special_cases_override` patches
        special cases by name; `_comment` ignored). Used for fixtures and for multi-document briefs."""
        with open(paths[0]) as f:
            d = json.load(f)
        for p in paths[1:]:
            with open(p) as f:
                d = merge_overlay(d, json.load(f))
        return cls.from_dict(d)

    def band_for(self, days_late: int) -> Band | None:
        for b in self.bands:
            if b.days_late_min <= days_late <= b.days_late_max:
                return b
        return None


@dataclass
class PromptSet:
    """LLM-authored instruction text per template stage. Keys are stage names used by compile.py.
    Prompts reference {{variables}} the code nodes set and never restate numbers the code computed."""
    system: str = ""
    stages: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PromptSet":
        return cls(system=d.get("system", ""), stages=dict(d.get("stages", {})))


# ---------------------------------------------------------------------------------------------
def merge_overlay(base: dict, overlay: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in overlay.items():
        if k == "_comment":
            continue
        if k == "special_cases_override":
            by_name = {sc["name"]: sc for sc in out.get("special_cases", [])}
            for name, patch in v.items():
                if name in by_name:
                    by_name[name].update(patch)
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_overlay(out[k], v)
        else:
            out[k] = v
    return out


def _build(cls, d):
    """Recursive dataclass constructor from a dict; tolerant of missing keys, strict on unknown ones."""
    if not dataclasses.is_dataclass(cls):
        return d
    kwargs = {}
    fields = {f.name: f for f in dataclasses.fields(cls)}
    unknown = set(d) - set(fields)
    if unknown:
        raise ValueError(f"{cls.__name__}: unknown keys {sorted(unknown)}")
    for name, f in fields.items():
        if name not in d:
            continue
        v = d[name]
        t = f.type if not isinstance(f.type, str) else f.type
        kwargs[name] = _coerce(t, v)
    return cls(**kwargs)


_LISTS = {
    "list[IdentityRequirement]": IdentityRequirement, "list[Band]": Band, "list[Attempt]": Attempt,
    "list[SpecialCase]": SpecialCase, "list[OutcomeRow]": OutcomeRow,
}
_OBJS = {
    "Span": Span, "IdentityPolicy": IdentityPolicy, "CallbackPolicy": CallbackPolicy, "ThirdPartyPolicy": ThirdPartyPolicy,
    "Calendar": Calendar, "AmountPolicy": AmountPolicy, "DatePolicy": DatePolicy, "OutcomePolicy": OutcomePolicy,
    "NotesPolicy": NotesPolicy, "MultiProductPolicy": MultiProductPolicy, "Phrases": Phrases, "PromiseWritePolicy": PromiseWritePolicy,
}


def _coerce(t, v):
    t = str(t)
    if t in _LISTS:
        return [_build(_LISTS[t], x) for x in v]
    if t in _OBJS:
        return _build(_OBJS[t], v)
    if t.startswith("tuple[") and isinstance(v, list):
        return tuple(v)
    return v


# ---------------------------------------------------------------------------------------------
def validate(ir: PolicyIR, tool_enums: dict[str, dict[str, list[str]]] | None = None) -> list[str]:
    """Structural problems the compiler cannot work around. `tool_enums` is {operation: {field: [values]}}
    from the OpenAPI document; when given, every outcome/reason/queue/note reason in the IR must be in it."""
    errs: list[str] = []
    if not ir.identity.requirements:
        errs.append("identity.requirements is empty")
    for r in ir.identity.requirements:
        if r.answer_format not in ANSWER_FORMATS:
            errs.append(f"identity requirement {r.field}: bad answer_format {r.answer_format}")
    if not ir.bands:
        errs.append("bands is empty")
    for b in ir.bands:
        if b.deadline.get("kind") not in DEADLINE_KINDS:
            errs.append(f"band {b.name}: unknown deadline kind {b.deadline.get('kind')}")
        if b.deadline.get("kind") != "nth_business_day" and b.deadline.get("adjustment") not in ("none", "following", "preceding"):
            errs.append(f"band {b.name}: explicit deadline adjustment required")
        if b.deadline.get("kind") == "end_of_month" and b.deadline.get("basis") not in ("calendar", "business"):
            errs.append(f"band {b.name}: explicit end_of_month basis required")
        for a in b.attempts:
            if a.amount not in ATTEMPT_AMOUNT_SOURCES or a.date not in ATTEMPT_DATE_SOURCES:
                errs.append(f"band {b.name}: bad attempt {a}")
    if not ir.amounts.floors:
        errs.append("amounts.floors is empty")
    o = ir.outcomes
    for name in ("promise_outcome", "paid_outcome", "transfer_outcome", "no_promise_outcome"):
        if not getattr(o, name):
            errs.append(f"outcomes.{name} is empty")
    if ir.notes.enabled and not ir.notes.reasons:
        errs.append("notes enabled without reasons")
    for h in ir.calendar.holidays:
        if len(h) != 10 or h[4] != "-" or h[7] != "-":
            errs.append(f"calendar holiday not ISO: {h}")
    if tool_enums:
        close = tool_enums.get("close_call", {})
        allowed_outcomes = set(close.get("outcome", []))
        if allowed_outcomes:
            for row in o.table:
                if row.outcome not in allowed_outcomes:
                    errs.append(f"outcome {row.outcome} not in close_call enum")
        queues = set(tool_enums.get("transfer_to_agent", {}).get("queue", []))
        if queues:
            for sc in ir.special_cases:
                q = sc.action.get("queue") or sc.offer_transfer_queue
                if q and q not in queues:
                    errs.append(f"special case {sc.name}: queue {q} not in transfer_to_agent enum")
        fields = set(tool_enums.get("verify_identity", {}).get("field", []))
        if fields:
            for r in ir.identity.requirements:
                if r.field not in fields:
                    errs.append(f"identity field {r.field} not in verify_identity enum")
        reasons = set(tool_enums.get("add_note", {}).get("reason", []))
        if reasons and ir.notes.enabled:
            for r in ir.notes.reasons:
                if r not in reasons:
                    errs.append(f"note reason {r} not in add_note enum")
    return errs


if __name__ == "__main__":
    import sys
    ir = PolicyIR.load(sys.argv[1])
    problems = validate(ir)
    print("\n".join(problems) or "ok")
    sys.exit(1 if problems else 0)
