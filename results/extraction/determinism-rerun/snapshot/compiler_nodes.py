"""Freya node constructors and speech extraction schemas."""
from compiler_openapi import ToolSpec

MIN_CONF = 0.5
WEEKDAY_ENUM = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def always(target):
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}


def on_next(target, value=None):
    return {"target_node": target, "description": "next is " + (value or target),
            "condition": {"logic": "or", "conditions": [{"variable": "next", "operator": "equals", "operand": value or target}]}}


def guarded_dispatch(target, flag):
    """Transition into an engine-fired call only when `next` names it AND the previous result flag was consumed
    (the code node clears it). If the code node was skipped, the stale flag blocks a repeat call instead of a loop."""
    return {"target_node": target, "description": f"{target}, previous result consumed",
            "condition": {"logic": "or", "conditions": [{"logic": "and", "conditions": [
                {"variable": "next", "operator": "equals", "operand": target},
                {"variable": flag, "operator": "not_equals", "operand": "true"},
                {"variable": flag, "operator": "not_equals", "operand": "True"}]}]}}


def on_enum(var, values, target):
    return {"target_node": target, "description": f"{var} decided",
            "condition": {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": x} for x in values]}}


def code_node(name, code, targets, default=None):
    assert "{{" not in code and "}}" not in code, f"code node {name} contains template braces"
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": default or targets[-1],
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                         "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code},
                                                                         "timeout_ms": {"type": "number", "default": 40000}}}}}],
        "transitions": [on_next(t) for t in targets] + [always(default or targets[-1])],
    }


def api_node(name, tool: ToolSpec, body_values: dict, next_node, mapping: list, on_enter=None, retries=0):
    """Engine-fired bank call. `body_values` maps body field -> baked default ('{{var}}' or literal).
    Fields not in body_values are omitted (so an optional field like `reason` can be left out)."""
    props = {}
    for field, val in body_values.items():
        spec = dict(tool.body_props.get(field, {"type": "string"}))
        spec = {k: v for k, v in spec.items() if k in ("type", "enum", "description", "format")}
        spec["default"] = val
        props[field] = spec
    required = [r for r in tool.required if r in props]
    return {
        "name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": next_node,
        "on_enter": on_enter or {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "config": {"timeoutMs": 12000, "maxRetries": retries},
                         "function": {"name": tool.name, "handler": "__function__:api_call", "description": tool.name,
                                      "parameters": {"type": "object", "properties": {
                                          "url": {"type": "string", "default": tool.url},
                                          "method": {"type": "string", "default": tool.method},
                                          "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                                          "body": {"type": "object", "properties": props, "required": required}}}}}],
        "response_mapping": mapping,
        "transitions": [always(next_node)],
    }


def conv_node(name, task, extraction, transitions, on_enter=None, first_only=False, max_turns=20, max_turn_target=None):
    n = {
        "name": name, "node_type": "conversation", "task_message": task, "on_enter": on_enter or {"type": "llm"},
        "on_enter_first_entry_only": first_only, "extraction_schema": extraction, "tools": [],
        "max_node_turns": max_turns, "transitions": list(transitions),
    }
    if max_turn_target:
        n["max_turn_transition"] = max_turn_target
    return n


def end_node(name="end"):
    return {"name": name, "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                         "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}}}


CORRECTION_NOTE = " If the customer corrects themselves ('the 21st, sorry, the 20th'; '600, I mean 637.50'), use the corrected value only."


def ext(name, type_, desc, enum=None, pattern=None):
    """Extraction variable. The platform validates EVERY write to a variable (also from code) against this schema,
    so each schema accepts an explicit "empty" value the runtime can clear to: 'none' in enums, 0 for numbers,
    '' for strings (patterns allow the empty string)."""
    if type_ in ("integer", "float") or name.endswith(("_kind", "_weekday", "_digits", "_time")):
        desc = desc.rstrip() + CORRECTION_NOTE
    e = {"name": name, "type": type_, "description": desc, "min_confidence": MIN_CONF}
    if enum:
        e["enum_values"] = list(enum) + ([] if "none" in enum else ["none"])
    if pattern:
        e["validation_pattern"] = "^$|" + pattern
    return e


PAYMENT_ONLY = " Only a day the customer offers as a payment day counts; a date mentioned for any other reason (an event, a wedding, a trip, a salary date without an offer to pay) is NOT a payment date — leave empty."


def date_ext(prefix, what, *, payment=True):
    """Structured date expression; resolved in code against the simulated `now` (never by the extractor)."""
    restriction = PAYMENT_ONLY if payment else " Only a day offered for reaching the customer counts; unrelated dates do not count."
    return [
        ext(prefix + "_kind", "string", f"How {what} was expressed. today / tomorrow / weekday (a day name, with or without 'this' or 'next') / "
            "date (a day of the month, with or without a month) / vague (a period without an exact day: next week, end of the month, when my salary comes, "
            "the week after next, in a few days) / none if no relevant day was mentioned." + restriction, ["today", "tomorrow", "weekday", "date", "vague", "none"]),
        ext(prefix + "_weekday", "string", "The weekday name if a weekday was said.", WEEKDAY_ENUM),
        ext(prefix + "_relative", "string", "'next' if the customer said 'next <weekday>', otherwise 'this' (also for a bare weekday name).", ["this", "next"]),
        ext(prefix + "_day", "integer", "The day of the month as a number (1-31) if a date was said, for example 26 for 'Monday the 26th' or 'the twenty-sixth'."),
        ext(prefix + "_month", "integer", "The month as a number (1-12) if the customer named a month, else leave empty."),
        ext(prefix + "_year", "integer", "The year as a 4-digit number only if the customer said one."),
    ]
