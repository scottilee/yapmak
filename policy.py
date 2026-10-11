"""Structural policy IR: the small, typed part of a brief that the workflow compiler parameterizes.

Two layers make up a compiled policy (plan §3.1):
  1. this structural IR (numbers, calendars, enums, rule shapes) with a source span per value,
  2. LLM-authored prompt text per template stage (see `PromptSet`).

Nothing in this module knows any bank's values. Practice fixtures live in tests/fixtures/*.policy.json.

The IR is plain JSON-serializable dataclasses so that an extractor can emit it, the auditor can diff it
against the source text, and the compiler can embed its values into code nodes.
"""
from __future__ import annotations

import datetime
import dataclasses
import json
import re
from dataclasses import dataclass, field
from typing import Any, get_args, get_origin, get_type_hints

# ---------------------------------------------------------------------------------------------
# Deadline-rule DSL. Anything the compiler cannot express goes to PolicyIR.unresolved.
#   {"kind": "nth_business_day", "n": 12}      the n-th business day after today
#   {"kind": "calendar_days", "n": 14}         today + n calendar days; explicit adjustment required
#   {"kind": "fixed_date", "date": "YYYY-MM-DD"}
#   {"kind": "end_of_month"}                   explicit basis=calendar|business and adjustment required
DEADLINE_KINDS = ("nth_business_day", "calendar_days", "fixed_date", "end_of_month", "day_of_month", "earliest", "latest")
FLOOR_RULE_KINDS = ("field", "percent", "fixed", "max_of")

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
    weekdays: list[int] = field(default_factory=list)   # only these weekdays (Monday=0 … Sunday=6) may be booked; empty = any business day
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
    missing_date_parts: str = "unresolved"  # "unresolved" (documents silent) and "next_occurrence" resolve a bare day to its next occurrence; "ask" asks for the month
    next_weekday: str = "coming"            # "next Friday" said while Friday is still ahead this week: "coming" = this week's; "following_week" = next week's
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
    # product type (or "*" for every type) -> floor rule when the floor is not a bank field:
    #   {"kind": "field", "field": <response property>} | {"kind": "percent", "percent": 20, "min_amount": 0} | {"kind": "fixed", "amount": 50}
    # a percent rule applies to the past-due amount; the floor never exceeds the full amount. `floors` stays the shorthand for field rules.
    floor_rules: dict[str, dict[str, Any]] = field(default_factory=dict)
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
    past_deadline: str = "next_business_day"   # when the computed deadline is already behind us: next_business_day (offer the first business day) | no_promise (no eligible date: the product gets no promise)
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
    # field names the documents state for the tool API, "<tool>.<slot>": property, e.g. {"get_account.past_due": "outst"};
    # the compiler honours one only when that property exists in the schema, otherwise it matches names by meaning
    api_fields: dict[str, str] = field(default_factory=dict)
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
KNOWN_SPECIAL_CASES = ("already_paid", "dispute", "hardship", "restructuring", "human", "scam", "refuse_to_talk")


def unknown_special_cases(ir: PolicyIR) -> list[str]:
    """Special cases whose name the template cannot route (the extractor is told to map onto the known names); surfaced in the trace."""
    return [sc.name for sc in ir.special_cases if sc.name not in KNOWN_SPECIAL_CASES]


def defaulted_operative_fields(ir: PolicyIR) -> list[str]:
    """Operative values that equal the schema default while their section cites no source text: a possible extraction gap
    (the documents may simply agree with the default, so this is a trace warning, never a validation error)."""
    out = []
    if not ir.identity.source.text and ir.identity.wrong_answer_limit == 3:
        out.append("identity.wrong_answer_limit=3")
    if not ir.identity.source.text and ir.identity.holder_confirmation_asks == 2:
        out.append("identity.holder_confirmation_asks=2")
    cb = ir.third_party.callback
    if cb.enabled and not cb.source.text and (cb.days, cb.start, cb.end) == ("today_or_next_business_day", "10:00", "19:00"):
        out.append("third_party.callback window=default")
    if not ir.promise_write.source.text and ir.promise_write.retry_on_failure == 1:
        out.append("promise_write.retry_on_failure=1")
    if not ir.multi_product.source.text and ir.multi_product.max_products == 3:
        out.append("multi_product.max_products=3")
    if not ir.calendar.source.text and not ir.calendar.holidays:
        out.append("calendar.holidays=[]")
    return out


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
    """Typed JSON construction; missing fields use dataclass defaults, unknown/wrong types fail."""
    if not isinstance(d, dict):
        raise ValueError(f"{cls.__name__}: expected an object")
    fields = {f.name: f for f in dataclasses.fields(cls)}
    unknown = set(d) - set(fields)
    if unknown:
        raise ValueError(f"{cls.__name__}: unknown keys {sorted(unknown)}")
    hints = get_type_hints(cls)
    kwargs = {}
    for name, value in d.items():
        try:
            kwargs[name] = _coerce(hints[name], value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"{cls.__name__}.{name}: {e}") from e
    try:
        return cls(**kwargs)
    except TypeError as e:
        raise ValueError(str(e)) from e


def _coerce(t, value):
    if t is Any:
        return value
    if dataclasses.is_dataclass(t):
        return _build(t, value)
    origin, args = get_origin(t), get_args(t)
    if origin is list and isinstance(value, list):
        return [_coerce(args[0], v) for v in value]
    if origin is dict and isinstance(value, dict):
        return {_coerce(args[0], k): _coerce(args[1], v) for k, v in value.items()}
    if origin is tuple and isinstance(value, (list, tuple)) and len(value) == len(args):
        return tuple(_coerce(kind, v) for kind, v in zip(args, value))
    if t in (str, int, float, bool) and type(value) is t:
        return value
    raise ValueError(f"expected {t}, got {type(value).__name__}")


# ---------------------------------------------------------------------------------------------
def _validate_deadline_rule(rule: dict, band: str, errs: list, iso_date) -> None:
    """Checks for one simple deadline rule (also applied to each child of earliest/latest)."""
    kind = rule.get("kind")
    if kind not in DEADLINE_KINDS or kind in ("earliest", "latest"):
        errs.append(f"band {band}: unknown or nested deadline kind {kind}")
        return
    if kind in ("nth_business_day", "calendar_days"):
        n = rule.get("n")
        if type(n) is not int or n < (1 if kind == "nth_business_day" else 0):
            errs.append(f"band {band}: invalid deadline n")
    if kind == "fixed_date" and not iso_date(rule.get("date")):
        errs.append(f"band {band}: invalid fixed deadline date")
    if kind != "nth_business_day" and rule.get("adjustment") not in ("none", "following", "preceding"):
        errs.append(f"band {band}: explicit deadline adjustment required")
    if kind == "end_of_month" and rule.get("basis") not in ("calendar", "business"):
        errs.append(f"band {band}: explicit end_of_month basis required")
    if kind in ("end_of_month", "day_of_month"):
        mo = rule.get("month_offset", 0)
        if type(mo) is not int or not 0 <= mo <= 12:
            errs.append(f"band {band}: month_offset must be an integer 0..12")
    if kind == "day_of_month":
        dd = rule.get("day")
        if type(dd) is not int or not 1 <= dd <= 31:
            errs.append(f"band {band}: day_of_month needs day 1..31")


def validate(ir: PolicyIR, tool_enums: dict[str, dict[str, list[str]]] | None = None) -> list[str]:
    """Structural problems the compiler cannot work around. `tool_enums` is {operation: {field: [values]}}
    from the OpenAPI document; when given, every outcome/reason/queue/note reason in the IR must be in it."""
    errs: list[str] = []
    def iso_date(value):
        try:
            return isinstance(value, str) and datetime.date.fromisoformat(value).isoformat() == value
        except (ValueError, TypeError):
            return False

    if not ir.calendar.business_days or any(type(d) is not int or not 0 <= d <= 6 for d in ir.calendar.business_days):
        errs.append("calendar.business_days must contain weekdays 0..6")
    for name, value, minimum in (
        ("identity.wrong_answer_limit", ir.identity.wrong_answer_limit, 1),
        ("identity.holder_confirmation_asks", ir.identity.holder_confirmation_asks, 1),
        ("multi_product.max_products", ir.multi_product.max_products, 1),
        ("promise_write.retry_on_failure", ir.promise_write.retry_on_failure, 0),
    ):
        if type(value) is not int or value < minimum:
            errs.append(f"{name} must be an integer >= {minimum}")
    if not ir.identity.requirements:
        errs.append("identity.requirements is empty")
    for r in ir.identity.requirements:
        if r.answer_format not in ANSWER_FORMATS:
            errs.append(f"identity requirement {r.field}: bad answer_format {r.answer_format}")
        if r.answer_format == "date" and r.numeric_date_order not in ("dmy", "mdy"):
            errs.append(f"identity requirement {r.field}: numeric_date_order must be dmy or mdy")
        if r.answer_format == "digits" and (type(r.digits) is not int or r.digits < 1):
            errs.append(f"identity requirement {r.field}: digits must be a positive integer for the digits format")
    cb = ir.third_party.callback
    if cb.enabled:
        if cb.days not in ("today", "next_business_day", "today_or_next_business_day"):
            errs.append("third_party.callback.days must be today, next_business_day or today_or_next_business_day")
        for name, value in (("start", cb.start), ("end", cb.end)):
            if not isinstance(value, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
                errs.append(f"third_party.callback.{name} must be HH:MM (24-hour), got {value!r}")
        if isinstance(cb.start, str) and isinstance(cb.end, str) and re.fullmatch(r"\d\d:\d\d", cb.start) and re.fullmatch(r"\d\d:\d\d", cb.end) and cb.start > cb.end:
            errs.append("third_party.callback.start must not be after end")
    if not ir.bands:
        errs.append("bands is empty")
    for i, b in enumerate(ir.bands):
        if type(b.days_late_min) is not int or type(b.days_late_max) is not int or not 0 <= b.days_late_min <= b.days_late_max:
            errs.append(f"band {b.name}: invalid days-late range")
        else:
            for previous in ir.bands[:i]:
                if type(previous.days_late_min) is int and type(previous.days_late_max) is int and max(b.days_late_min, previous.days_late_min) <= min(b.days_late_max, previous.days_late_max):
                    errs.append(f"band {b.name}: overlaps {previous.name}")
        if not isinstance(b.deadline, dict):
            errs.append(f"band {b.name}: deadline must be an object")
            continue
        kind = b.deadline.get("kind")
        rules_to_check = [b.deadline]
        if kind in ("earliest", "latest"):
            subs = b.deadline.get("rules")
            if not isinstance(subs, list) or len(subs) < 2 or any(not isinstance(r, dict) or r.get("kind") not in DEADLINE_KINDS or r.get("kind") in ("earliest", "latest") for r in subs):
                errs.append(f"band {b.name}: {kind} needs a list of at least two simple deadline rules")
                rules_to_check = []
            else:
                rules_to_check = list(subs)
        for sub in rules_to_check:
            _validate_deadline_rule(sub, b.name, errs, iso_date)
        for a in b.attempts:
            if a.amount not in ATTEMPT_AMOUNT_SOURCES or a.date not in ATTEMPT_DATE_SOURCES:
                errs.append(f"band {b.name}: bad attempt {a}")
    if not ir.amounts.floors and not ir.amounts.floor_rules:
        errs.append("amounts.floors is empty (and no floor_rules)")
    for t, rule in (ir.amounts.floor_rules or {}).items():
        if not isinstance(rule, dict) or rule.get("kind") not in FLOOR_RULE_KINDS:
            errs.append(f"amounts.floor_rules[{t}]: kind must be one of {FLOOR_RULE_KINDS}")
            continue
        if rule["kind"] == "field" and not rule.get("field"):
            errs.append(f"amounts.floor_rules[{t}]: field rule needs a response property name")
        if rule["kind"] == "percent" and not (isinstance(rule.get("percent"), (int, float)) and 0 < rule["percent"] <= 100):
            errs.append(f"amounts.floor_rules[{t}]: percent must be in (0, 100]")
        if rule["kind"] == "fixed" and not (isinstance(rule.get("amount"), (int, float)) and rule["amount"] > 0):
            errs.append(f"amounts.floor_rules[{t}]: fixed rule needs a positive amount")
        if rule["kind"] == "max_of" and not (rule.get("field") and isinstance(rule.get("percent"), (int, float)) and 0 < rule["percent"] <= 100):
            errs.append(f"amounts.floor_rules[{t}]: max_of needs a field and a percent in (0, 100]")
    if ir.dates.past_deadline not in ("next_business_day", "no_promise"):
        errs.append("dates.past_deadline must be next_business_day or no_promise")
    names = {sc.name for sc in ir.special_cases}
    if not ir.phrases.opening:
        errs.append("phrases.opening is empty: write the opening sentence the documents require")
    if "already_paid" in names and not (ir.phrases.already_paid_sentence or next(sc.say for sc in ir.special_cases if sc.name == "already_paid")):
        errs.append("already_paid: neither phrases.already_paid_sentence nor special_cases[already_paid].say says what to tell the customer")
    o = ir.outcomes
    for name in ("promise_outcome", "no_promise_outcome"):
        if not getattr(o, name):
            errs.append(f"outcomes.{name} is empty")
    # a paid / transfer outcome is only required when some path needs it and supplies no outcome of its own:
    # documents without an already-paid rule or without any transfer have none, and the builder must not invent one
    needs_paid = any(sc.name == "already_paid" and not (sc.action or {}).get("outcome") for sc in ir.special_cases)
    if needs_paid and not o.paid_outcome:
        errs.append("outcomes.paid_outcome is empty although the already_paid case closes without an outcome of its own")
    needs_transfer = any(((sc.action or {}).get("type") == "transfer" and not (sc.action or {}).get("outcome")) or (sc.offer_transfer_queue and not sc.offer_outcome[0]) for sc in ir.special_cases)
    if needs_transfer and not o.transfer_outcome:
        errs.append("outcomes.transfer_outcome is empty although a transfer path supplies no outcome of its own")
    if ir.notes.enabled and not ir.notes.reasons:
        errs.append("notes enabled without reasons")
    # Template-behaviour switches: false means the documents ask for something the fixed template cannot do.
    # Those deviations must surface as unresolved[] entries (and block the affected action), never as a silently ignored flag.
    for name, value, why in (
        ("amounts.full_first", ir.amounts.full_first, "the engine always asks for the full amount before any floor"),
        ("amounts.never_ask_how_much", ir.amounts.never_ask_how_much, "the dialogue is instructed never to ask the customer for an amount"),
        ("amounts.accept_between_floor_and_full", ir.amounts.accept_between_floor_and_full, "the proposal validator accepts floor..full by construction"),
        ("promise_write.one_promise_per_product", ir.promise_write.one_promise_per_product, "the write loop records at most one promise per product"),
        ("multi_product.state_all_before_asking", ir.multi_product.state_all_before_asking, "the debt statement always lists every product first"),
        ("multi_product.ask_all_today_once", ir.multi_product.ask_all_today_once, "the pay-all-today question is always asked once for the batch"),
        ("multi_product.per_product_attempts", ir.multi_product.per_product_attempts, "attempt counters are always per product"),
        ("multi_product.one_confirmation_for_batch", ir.multi_product.one_confirmation_for_batch, "confirmation is always a single batch read-back"),
        ("multi_product.recorded_promises_survive_transfer", ir.multi_product.recorded_promises_survive_transfer, "recorded promises always stay when the call transfers"),
    ):
        if value is False:
            errs.append(f"{name} must be true: {why}; express the deviation in unresolved[] instead")
    if ir.identity.wrong_count_source not in ("api", "code"):
        errs.append(f"identity.wrong_count_source must be 'api' or 'code', not {ir.identity.wrong_count_source!r}")
    for sc in ir.special_cases:
        if not str(sc.trigger or "").strip():
            errs.append(f"special case {sc.name}: trigger is empty (describe in words what the customer says)")
    for h in ir.calendar.holidays:
        if not iso_date(h):
            errs.append(f"calendar holiday not ISO: {h}")
    # every close reason a special case uses must be one the outcome table allows for that outcome
    allowed = {row.outcome: set(row.reasons) for row in o.table}
    for sc in ir.special_cases:
        a = sc.action or {}
        if a.get("type") in ("close", "transfer") and a.get("outcome") in allowed and a.get("reason") and a["reason"] not in allowed[a["outcome"]]:
            errs.append(f"special case {sc.name}: reason {a['reason']} is not listed for outcome {a['outcome']} in the outcome table")
        if sc.offer_outcome and sc.offer_outcome[0] in allowed and sc.offer_outcome[1] and sc.offer_outcome[1] not in allowed[sc.offer_outcome[0]]:
            errs.append(f"special case {sc.name}: offer reason {sc.offer_outcome[1]} is not listed for outcome {sc.offer_outcome[0]}")
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
    close_enums = (tool_enums or {}).get("close_call", {})
    outcome_enum = set(close_enums.get("outcome", []))
    reason_enum = set(close_enums.get("reason", []))

    def check_pair(label, outcome, reason="", optional=False):
        if optional and not outcome and not reason:
            return
        if not outcome or (outcome_enum and outcome not in outcome_enum) or outcome not in allowed:
            errs.append(f"{label}: unknown outcome {outcome!r}")
        if reason and ((reason_enum and reason not in reason_enum) or reason not in allowed.get(outcome, set())):
            errs.append(f"{label}: reason {reason!r} not allowed for {outcome!r}")

    for row in o.table:
        for reason in row.reasons:
            if reason_enum and reason not in reason_enum:
                errs.append(f"outcome {row.outcome}: reason {reason!r} not in close_call enum")
    for name in ("promise_outcome", "no_promise_outcome"):
        check_pair("outcomes." + name, getattr(o, name))
    for name in ("paid_outcome", "transfer_outcome"):
        check_pair("outcomes." + name, getattr(o, name), optional=True)
    for name in ("service_error_reason", "refused_reason"):
        check_pair("outcomes." + name, o.no_promise_outcome, getattr(o, name))
    for obj in (ir.identity, ir.third_party, ir.third_party.callback):
        for f in dataclasses.fields(obj):
            if f.name.endswith("_outcome"):
                pair = getattr(obj, f.name)
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    errs.append(f"{type(obj).__name__}.{f.name}: expected [outcome, reason]")
                else:
                    check_pair(f"{type(obj).__name__}.{f.name}", *pair)
    for sc in ir.special_cases:
        action = sc.action
        if action.get("type") in ("close", "transfer"):
            check_pair(f"special case {sc.name}", action.get("outcome"), action.get("reason", ""))
        if len(sc.offer_outcome) != 2:
            errs.append(f"special case {sc.name}: offer_outcome must have two entries")
        else:
            check_pair(f"special case {sc.name} offer", *sc.offer_outcome, optional=True)
        note_reasons = set((tool_enums or {}).get("add_note", {}).get("reason", []))
        if action.get("type") == "note" and note_reasons and action.get("reason") not in note_reasons:
            errs.append(f"special case {sc.name}: invalid note reason")
        queues = set((tool_enums or {}).get("transfer_to_agent", {}).get("queue", []))
        for queue in (action.get("queue"), sc.offer_transfer_queue):
            if queue and queues and queue not in queues:
                errs.append(f"special case {sc.name}: invalid transfer queue {queue}")
    return errs


if __name__ == "__main__":
    import sys
    ir = PolicyIR.load(sys.argv[1])
    problems = validate(ir)
    print("\n".join(problems) or "ok")
    sys.exit(1 if problems else 0)
