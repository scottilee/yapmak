"""Provenance checker: does every value in an extracted policy IR trace back to the documents it cites?

    .venv/bin/python scripts/check_provenance.py [policy.json ...] [--report results/provenance/README.md]

Default inputs: out/*.policy.json (extractor output). Hand-written IRs (tests/fixtures, results/audit/synthetic) cite rule
numbers instead of quotes and are expected to fail the span check. When `source_docs` lists no OpenAPI file, the one next
to the brief (or tools/openapi.json) is read too, since field names and enum values legitimately come from it.
Per IR it checks:
  FAIL span-missing   a cited `source.text` is not a quote of the cited document (under 40% of its word 4-grams occur there)
  WARN loose-quote    40-75% of the quoted words occur in the document (edited or spliced quote)
  WARN cross-doc      the quote is real but spliced from several documents while citing one
  FAIL doc-missing    the cited document cannot be found next to the IR's `source_docs`
  FAIL value-absent   an operative value (field name, count, time, date, outcome, reason, queue, product type, floor
                      property) appears in neither the cited span nor any source document (OpenAPI enums included)
  WARN uncited        a cited doc is not one of the IR's `source_docs`
  WARN superseded?    the value is cited from an earlier document while a later one (memo/addendum) also discusses the topic
  WARN paraphrase     a phrase marked verbatim is not found word for word in the documents
Exit 1 if any FAIL. Spans that cite rule ids instead of quotes ("MARCUS V5") show up as span-missing: that is the point.
"""
from __future__ import annotations

import glob
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
NUM_WORDS = {"one": 1, "once": 1, "two": 2, "twice": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30, "forty-five": 45, "sixty": 60, "ninety": 90}
MONTHS = "january february march april may june july august september october november december".split()


def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    s = re.sub(r"[`*_>#|]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Docs:
    def __init__(self, ir_path: pathlib.Path, source_docs: list[str]):
        self.texts: dict[str, str] = {}
        self.order: list[str] = []
        self.enums: set[str] = set()
        for d in source_docs:
            p = self.resolve(ir_path, d)
            if p:
                raw = p.read_text(errors="replace")
                self.texts[d] = norm(raw)
                self.order.append(d)
                if p.suffix == ".json":
                    self.enums |= set(map(str, _enum_values(json.loads(raw))))
        if not any(d.endswith(".json") for d in self.texts):          # the tool API is a source too: field names and enums come from it
            brief = next((self.resolve(ir_path, d) for d in source_docs if self.resolve(ir_path, d)), None)
            api = None
            if brief:                                                   # the sibling OpenAPI that shares the brief's name prefix
                stem = brief.stem.split("-brief")[0].split("brief")[0]
                sibs = sorted(brief.parent.glob("*openapi*.json"), key=lambda q: (not q.name.startswith(stem), q.name))
                api = sibs[0] if sibs and (sibs[0].name.startswith(stem) or len(sibs) == 1) else None
            api = api or (ROOT / "tools" / "openapi.json")
            if api.is_file():
                raw = api.read_text(errors="replace")
                self.texts[str(api.relative_to(ROOT))] = norm(raw)
                self.enums |= set(map(str, _enum_values(json.loads(raw))))
        self.all_text = " \n ".join(self.texts.values())

    @staticmethod
    def resolve(ir_path: pathlib.Path, doc: str) -> pathlib.Path | None:
        cands = [ROOT / doc, ir_path.parent / doc, ir_path.parent / pathlib.Path(doc).name]
        return next((c for c in cands if c.is_file()), None)

    def find(self, doc: str, ir_path: pathlib.Path) -> str | None:
        if doc in self.texts:
            return self.texts[doc]
        base = pathlib.Path(doc).name
        for d, t in self.texts.items():                       # cited by basename
            if pathlib.Path(d).name == base:
                return t
        p = self.resolve(ir_path, doc)
        return norm(p.read_text(errors="replace")) if p else None

    def later_docs(self, doc: str) -> list[str]:
        base = pathlib.Path(doc).name
        idx = next((i for i, d in enumerate(self.order) if pathlib.Path(d).name == base), None)
        return [] if idx is None else [d for d in self.order[idx + 1:] if not d.endswith(".json")]


def _enum_values(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "enum" and isinstance(v, list):
                yield from v
            else:
                yield from _enum_values(v)
    elif isinstance(o, list):
        for v in o:
            yield from _enum_values(v)


def spans(o, path=""):
    if isinstance(o, dict):
        if set(o) == {"doc", "text"}:
            yield path, o
        else:
            for k, v in o.items():
                yield from spans(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from spans(v, f"{path}[{i}]")


def coverage(frag: str, text: str) -> float:
    """Share of the fragment's word 4-grams found verbatim in the document. Extractors join non-adjacent rules with a
    space, so exact substring is too strict; rule-id citations ("section 5", "MARCUS V5") score 0."""
    if frag in text:
        return 1.0
    words = frag.split()
    if len(words) < 4:
        return 0.0
    grams = [" ".join(words[i:i + 4]) for i in range(len(words) - 3)]
    return sum(g in text for g in grams) / len(grams)


def number_in(n, text: str) -> bool:
    if n is None or n == "":
        return True
    s = str(n)
    if re.search(rf"(?<![\d.]){re.escape(s)}(?![\d])", text):
        return True
    return any(v == int(float(s)) and re.search(rf"\b{w}\b", text) for w, v in NUM_WORDS.items()) if re.fullmatch(r"-?\d+(\.0+)?", s) else False


def date_forms(iso: str) -> list[str]:
    y, m, d = iso.split("-")
    mon = MONTHS[int(m) - 1]
    return [iso, f"{int(d)} {mon} {y}", f"{int(d)} {mon[:3]} {y}", f"{mon} {int(d)}, {y}", f"{mon} {int(d)} {y}", f"{int(d)}.{int(m)}.{y}", f"{int(d)}/{int(m)}/{y}", f"{int(m)}/{int(d)}/{y}"]


def check_ir(path: pathlib.Path) -> dict:
    ir = json.load(open(path))
    docs = Docs(path, ir.get("source_docs", []))
    out = {"ir": str(path.relative_to(ROOT)), "docs": list(docs.texts), "fail": [], "warn": [], "spans": 0, "ok_spans": 0}
    F, W = out["fail"].append, out["warn"].append
    if not docs.texts:
        F(f"doc-missing: none of {ir.get('source_docs')} found")
        return out
    span_by_path = {}
    for p, sp in spans(ir):
        out["spans"] += 1
        holder = p.rsplit(".", 1)[0] if p.endswith(".source") else p
        span_by_path[holder] = sp
        if not sp.get("doc") and not sp.get("text"):
            continue
        text = docs.find(sp["doc"], path)
        if text is None:
            F(f"doc-missing: {p} cites {sp['doc']!r}")
            continue
        if not any(pathlib.Path(d).name == pathlib.Path(sp["doc"]).name for d in docs.order):
            W(f"uncited: {p} cites {sp['doc']!r}, not in source_docs")
        frags = [norm(f) for f in re.split(r"\s*(?:\.\.\.|…)\s*", sp.get("text", "")) if norm(f)]
        scores = [(coverage(f, text), f) for f in frags]
        worst = min(scores, default=(1.0, ""))
        if worst[0] < 0.4 and coverage(worst[1], docs.all_text) >= 0.75:
            W(f"cross-doc quote: {p} cites {pathlib.Path(sp['doc']).name} but the words come from another source document too")
            out["ok_spans"] += 1
        elif worst[0] < 0.4:
            F(f"span-missing: {p} -> {worst[1][:90]!r} (quoted-text coverage {worst[0]:.0%})")
        elif worst[0] < 0.75:
            W(f"loose-quote: {p} -> {worst[1][:90]!r} (coverage {worst[0]:.0%})")
            out["ok_spans"] += 1
        else:
            out["ok_spans"] += 1
        for later in docs.later_docs(sp["doc"]):
            topic = {"identity": "wrong answer", "callback": "callback", "calendar": "holiday", "bands": "business day", "amounts": "minimum",
                     "notes": "note", "outcomes": "close", "promise_write": "create_promise", "multi_product": "product"}.get(holder.split(".")[0].split("[")[0], "")
            if topic and topic in docs.texts.get(later, ""):
                W(f"superseded?: {holder} cited from {pathlib.Path(sp['doc']).name} while {pathlib.Path(later).name} also mentions {topic!r}")

    def span_text(holder):
        sp = span_by_path.get(holder) or {}
        return norm(sp.get("text", "")) if sp else ""

    def need(holder, label, value, where="span+docs", forms=None):
        """The value must appear in the holder's span (or anywhere in the docs/enums when where == 'docs')."""
        if value in (None, "", [], 0) and not isinstance(value, (int, float)):
            return
        hay = span_text(holder) + " \n " + docs.all_text if where != "span" else span_text(holder)
        cands = forms or [norm(str(value))]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            ok = number_in(value, span_text(holder)) or (where != "span" and number_in(value, docs.all_text))
        else:
            ok = any(c in hay for c in cands) or str(value) in docs.enums
        if not ok:
            F(f"value-absent: {label} = {value!r} ({holder})")

    ident = ir.get("identity", {})
    for i, r in enumerate(ident.get("requirements", [])):
        h = f"identity.requirements[{i}]"
        need(h, "identity field", r.get("field"), forms=[norm(r["field"]), norm(r["field"].replace("_", " "))])
        if r.get("answer_format") == "digits":
            need(h, "digits count", r.get("digits"))
    need("identity", "wrong_answer_limit", ident.get("wrong_answer_limit"))
    for k in ("failed_outcome", "declined_outcome", "unclear_holder_outcome"):
        for v in ident.get(k) or []:
            need("identity", k, v, forms=[norm(v)])
    cb = ir.get("third_party", {}).get("callback", {})
    for k in ("start", "end"):
        if cb.get(k):
            hh = cb[k][:2].lstrip("0") or "0"
            need("third_party.callback", f"callback {k}", cb[k], forms=[cb[k], f"{int(hh)}:00", f"{int(hh)}.00", f"{int(hh)} ", f"{int(hh)}am", f"{int(hh)}pm", f"{int(hh) - 12}pm" if int(hh) > 12 else cb[k]])
    for k in ("scheduled_outcome", "no_callback_outcome"):
        for v in cb.get(k) or []:
            need("third_party.callback", k, v)
    tp = ir.get("third_party", {})
    for k in ("wrong_number_outcome", "deceased_outcome"):
        for v in tp.get(k) or []:
            need("third_party", k, v)
    for d in ir.get("calendar", {}).get("holidays", []):
        need("calendar", "holiday", d, forms=[norm(x) for x in date_forms(d)])
    for i, b in enumerate(ir.get("bands", [])):
        h = f"bands[{i}]"
        need(h, f"band {b.get('name')} days_late_min", b.get("days_late_min"), where="span")
        need(h, f"band {b.get('name')} days_late_max", b.get("days_late_max"), where="span")
        dl = b.get("deadline", {})
        if "n" in dl:
            need(h, f"band {b.get('name')} deadline n", dl["n"], where="span")
        if dl.get("date"):
            need(h, f"band {b.get('name')} fixed deadline", dl["date"], forms=[norm(x) for x in date_forms(dl["date"])])
    for t, prop in ir.get("amounts", {}).get("floors", {}).items():
        need("amounts", "product type", t, forms=[norm(t), norm(t.replace("_", " "))])
        need("amounts", "floor property", prop, forms=[norm(prop), norm(prop.replace("_", " "))])
    for row in ir.get("outcomes", {}).get("table", []):
        need("outcomes", "outcome", row.get("outcome"))
        for rr in row.get("reasons", []):
            need("outcomes", f"reason of {row.get('outcome')}", rr)
    for v in ir.get("notes", {}).get("reasons", []):
        need("notes", "note reason", v)
    for i, sc in enumerate(ir.get("special_cases", [])):
        h = f"special_cases[{i}]"
        for k in ("outcome", "reason", "queue"):
            if sc.get("action", {}).get(k):
                need(h, f"{sc.get('name')} {k}", sc["action"][k])
        if sc.get("offer_transfer_queue"):
            need(h, f"{sc.get('name')} offer queue", sc["offer_transfer_queue"])
    mp = ir.get("multi_product", {})
    if mp.get("max_products", 0) > 1:
        need("multi_product", "max_products", mp["max_products"])
    pw = ir.get("promise_write", {})
    if pw.get("retry_on_failure", 0) > 1:
        need("promise_write", "retry_on_failure", pw["retry_on_failure"])
    ph = ir.get("phrases", {})
    for k in ("opening", "debt_intro", "today_question", "all_today_question", "deceased_sentence", "failed_instruction", "after_promise_sentence", "already_paid_sentence"):
        v = ph.get(k) or (ir.get("third_party", {}).get(k) if k == "deceased_sentence" else ident.get(k) if k == "failed_instruction" else None)
        if v and "{{" not in v:
            core = norm(re.sub(r"[.!?\"]+$", "", v))
            if core not in docs.all_text:
                (F if (k == "opening" and ph.get("opening_verbatim")) else W)(f"paraphrase: phrases.{k} = {v[:70]!r} not word for word in the documents")
    return out


def main():
    argv = sys.argv[1:]
    report = None
    if "--report" in argv:
        i = argv.index("--report")
        report = pathlib.Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    paths = [pathlib.Path(a) for a in args] or sorted(ROOT / p for p in glob.glob("out/*.policy.json"))
    lines, any_fail = [], False
    for p in paths:
        r = check_ir(p.resolve())
        any_fail |= bool(r["fail"])
        lines.append(f"## {r['ir']}\n\ndocs: {r['docs']}  |  spans quoted and found: {r['ok_spans']}/{r['spans']}  |  FAIL {len(r['fail'])}  WARN {len(r['warn'])}\n")
        lines += [f"- FAIL {x}" for x in r["fail"]] + [f"- WARN {x}" for x in r["warn"]] + [""]
        print(f"{r['ir']}: spans {r['ok_spans']}/{r['spans']} found, FAIL {len(r['fail'])}, WARN {len(r['warn'])}")
        for x in r["fail"][:12]:
            print("   FAIL", x[:160])
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# Provenance check\n\nGenerated by `scripts/check_provenance.py` (see its docstring for the rules).\n\n" + "\n".join(lines))
        print("report:", report)
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
