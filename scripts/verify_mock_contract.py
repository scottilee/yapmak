#!/usr/bin/env python3
"""Verify the deployed mock answers every entry in test-customers.json verbatim.

For every customer, card and week listed in the file, calls the matching endpoint,
compares HTTP status and JSON body with the listed expectation, reports differences.
Read-only against the mock; does not touch mock/.
"""
import json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://yapmak-bank-mock.winter-mountain-4405.workers.dev"
FILE = "hidden/final/test-environment/test-customers.json"
PATH = {  # service -> deployed path (the worker serves /voice/v1/<service>, not /cards/list style)
    "cards.list": "/voice/v1/cards.list", "cards.balance": "/voice/v1/cards.balance",
    "contact.email.get": "/voice/v1/contact.email.get", "statement.pdf.send": "/voice/v1/statement.pdf.send",
    "statement.week.get": "/voice/v1/statement.week.get", "statement.week.decide": "/voice/v1/statement.week.decide",
    "statement.week.change": "/voice/v1/statement.week.change",
}

def calls():
    data = json.load(open(FILE))
    for c in data["customers"]:
        for svc, e in c["services"].items():
            if "http" in e:
                yield c["customerNo"], svc, None, None, e
            else:
                for card, ev in e.items():
                    if "http" in ev:
                        yield c["customerNo"], svc, card, None, ev
                    else:
                        for wk, ev2 in ev.items():
                            yield c["customerNo"], svc, card, wk, ev2

def diff_path(a, b, path="$"):
    if type(a) is not type(b) or (isinstance(a, (int, float, str, bool)) and a != b):
        return [f"{path}: expected {a!r} got {b!r}"[:200]]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: present={k in a}/{k in b}")
            else:
                out += diff_path(a[k], b[k], f"{path}.{k}")
            if len(out) > 5: break
        return out[:6]
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}[]: len {len(a)} vs {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)): out += diff_path(x, y, f"{path}[{i}]")
        return out[:6]
    return []

def post(path, q, timeout=60):
    req = urllib.request.Request(BASE + path, data=json.dumps(q).encode(),
                                 headers={"content-type": "application/json",
                                          "user-agent": "curl/8.7.1"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read()

def discover_paths():
    # the worker lists its routes in the unknown-route 404 body: "POST <path>" keys
    try:
        st, body = post("/__probe__", {})
        listed = json.loads(body).get("paths", [])
    except Exception:
        listed = []
    paths = [p.split(" ", 1)[1] for p in listed if p.startswith("POST ")]
    m = {}
    for svc in SERVICES:
        c = [p for p in paths if p.rstrip("/").endswith(svc)] or \
            [p for p in paths if p.rstrip("/").endswith(svc.replace(".", "/"))]
        m[svc] = c[0] if c else FALLBACK[svc]
    return m

FALLBACK = dict(PATH)
SERVICES = list(PATH)
PATH = {}  # resolved at start()

def run(one):
    cno, svc, card, wk, e = one
    q = {"customerNo": cno}
    if card is not None: q["cardNumber"] = card
    if wk is not None: q["newStatementWeek"] = int(wk)
    got_status, body = post(PATH[svc], q)
    try: got_body = json.loads(body)
    except Exception: got_body = body.decode("utf-8", "replace")
    ok_status = got_status == e["http"]
    ok_body = got_body == e["response"]
    if ok_status and ok_body: return {"customerNo": cno, "service": svc, "card": card, "week": wk, "ok": True}
    d = [] if ok_body else diff_path(e["response"], got_body)
    return {"customerNo": cno, "service": svc, "card": card, "week": wk, "ok": False,
            "expected": {"http": e["http"], "body": None if ok_body else e["response"]},
            "got": {"http": got_status, "body": None if ok_body else got_body},
            "diffs": ([] if ok_status else [f"status {e['http']} -> {got_status}"]) + d}

def main():
    global PATH
    PATH = discover_paths()
    print("resolved paths:", json.dumps(PATH))
    todo = list(calls())
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(run, todo))
    fails = [r for r in results if not r["ok"]]
    print(f"{len(results)} calls, {len(results)-len(fails)} match, {len(fails)} differ")
    for f in fails:
        print(json.dumps(f, ensure_ascii=False))
    json.dump({"base": BASE, "paths": PATH, "total": len(results), "failures": fails},
              open("results/audit/mock-verification.json", "w"), ensure_ascii=False, indent=1)
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
