"""Auditor tool: aggregate results/latency/calls/*.json into the latency tables.

    .venv/bin/python results/latency/analyze_calls.py [more.workflow.json ...]

Numbers only; no opinions. Writes README tables to stdout (piped into results/audit/latency/README content file).
"""
import json, pathlib, statistics, sys, collections

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

NODETYPE = {}
for wf in ("out/gen-a.workflow.json", "out/gen-ab.workflow.json"):
    for n, v in json.load(open(ROOT / wf))["nodes"].items():
        NODETYPE.setdefault(n, v["node_type"])

CODE = {"setup", "opening_route", "id_route_0", "id_route_1", "verify_after_0", "verify_after_1", "cb_route", "cb_after",
        "init_products", "neg_route", "readback_route", "write_step", "finalize", "notes_step", "close_after"}
API = {"verify_0", "verify_1", "get_account", "create_promise", "add_note", "schedule_callback", "transfer",
       "close_reason", "close_noreason", "close_retry"}
STAGE = {}
for s in ("opening", "opening_route", "ask_0", "ask_1", "id_route_0", "id_route_1", "verify_0", "verify_1",
          "verify_after_0", "verify_after_1", "transfer_after"):
    STAGE[s] = "identity"
for s in ("third_party", "cb_route", "cb_after", "schedule_callback"):
    STAGE[s] = "third_party"
STAGE["get_account"] = STAGE["init_products"] = "account_load"
for s in ("state_debt", "negotiate", "neg_route"):
    STAGE[s] = "negotiation"
for s in ("readback", "readback_route", "write_step", "create_promise", "notes_step", "add_note",
          "finalize", "close_reason", "close_noreason", "close_retry", "close_after", "end", "transfer"):
    STAGE[s] = "confirm_close"
STAGE["setup"] = "identity"


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def analyze(path):
    d = json.load(open(path))
    meta = json.loads(pathlib.Path(str(path).replace(".json", ".meta.json")).read_text())
    ms = []
    for m in d.get("messages", []):
        ts = f(m.get("secondsFromStart"))
        if ts is None:
            continue
        try:
            ev = json.loads(m.get("message") or "{}")
        except Exception:
            ev = {}
        ms.append((ts, m.get("role"), m.get("nodeId") or (ev or {}).get("node"), ev if isinstance(ev, dict) else {}))
    ms.sort(key=lambda x: x[0])
    # visit dwell: coalesce consecutive same-node messages
    visits = []
    for ts, role, node, ev in ms:
        if node is None:
            continue
        if visits and visits[-1][0] == node:
            visits[-1][2] = ts
        else:
            visits.append([node, ts, ts])
    dwell = collections.defaultdict(list)
    for node, t0, t1 in visits:
        dwell[node].append(t1 - t0)
    # code_exec pure run time and per-visit hop time (start->complete)
    execs = []
    open_fn = {}
    for ts, role, node, ev in ms:
        e = ev.get("event")
        if e == "function_call_start":
            open_fn[ev.get("function", "")] = ts
        elif e == "function_call_complete":
            t = open_fn.pop(ev.get("function", ""), None)
            if t is not None:
                execs.append((ev.get("function"), node, ts - t))
    # user->assistant turn latencies by assistant node; extraction spans by node
    turns, extr = [], collections.defaultdict(list)
    last_user = None
    ext_start = {}
    for ts, role, node, ev in ms:
        if role == "user":
            last_user, ext_start[node] = ts, {}
        elif role == "assistant" and last_user is not None:
            turns.append((node, ts - last_user))
            last_user = None
        elif ev.get("event") == "variable_extracted" and last_user is not None:
            k = node
            if k not in ext_start:
                ext_start[k] = ts
    for ts, role, node, ev in ms:
        pass
    # extraction total per turn: span user -> last variable_extracted before next assistant
    pend_u, ext_last, ext_span = None, {}, collections.defaultdict(list)
    for ts, role, node, ev in ms:
        if role == "user":
            pend_u, ext_last = ts, {}
        elif ev.get("event") == "variable_extracted" and pend_u is not None:
            ext_last[node] = ts
        elif role == "assistant" and pend_u is not None:
            if ext_last:
                last_node = max(ext_last, key=ext_last.get)
                ext_span[last_node].append(max(ext_last.values()) - pend_u)
            pend_u = None
    return meta, dwell, turns, ext_span


def q(xs):
    xs = sorted(xs)
    if not xs:
        return "-"
    med = statistics.median(xs)
    p95 = xs[min(len(xs) - 1, int(len(xs) * 0.95))]
    return f"n={len(xs)} med={med:.2f} p95={p95:.2f}"


def main():
    calls = sorted(HERE.glob("calls/*.json"))
    calls = [c for c in calls if not c.name.endswith(".meta.json")]
    recs = []
    for c in calls:
        try:
            recs.append(analyze(c))
        except Exception as e:
            print("skip", c.name, repr(e)[:80], file=sys.stderr)
    # bucket calls by their own median assistant-turn latency
    for meta, dwell, turns, ext in recs:
        ts = [t for _, t in turns]
        meta["_call_med"] = statistics.median(ts) if ts else None
    quiet = [r for r in recs if r[0]["_call_med"] is not None and r[0]["_call_med"] <= 6.0]
    loaded = [r for r in recs if r[0]["_call_med"] is not None and r[0]["_call_med"] > 6.0]
    print(f"calls={len(recs)} quiet(med turn<=6s)={len(quiet)} loaded(>6s)={len(loaded)}")
    files = collections.Counter((m["file"], m["window"]) for m, _, _, _ in recs)
    print("\n## sampled files:", dict(files))

    # visit dwell per node
    allnodes = sorted({n for _, d, _, _ in recs for n in d})
    print("\n### Visit dwell (seconds, per visit) — code nodes")
    print("| node | quiet | loaded |")
    print("|---|---|---|")
    for n in allnodes:
        if n in CODE or n == "setup":
            print(f"| {n} | {q([d for _, d, _, _ in quiet for d in d.get(n, [])])} | {q([d for _, d, _, _ in loaded for d in d.get(n, [])])} |")
    print("\n### Visit dwell — api_request nodes (bank HTTP included)")
    print("| node | quiet | loaded |")
    print("|---|---|---|")
    for n in allnodes:
        if n in API:
            print(f"| {n} | {q([d for _, d, _, _ in quiet for d in d.get(n, [])])} | {q([d for _, d, _, _ in loaded for d in d.get(n, [])])} |")
    print("\n### Assistant turn latency (user->agent), by stage")
    print("| stage | quiet | loaded |")
    print("|---|---|---|")
    for st in ("identity", "third_party", "negotiation", "confirm_close"):
        print(f"| {st} | {q([t for _, _, turns, _ in quiet for n, t in turns if STAGE.get(n) == st])} | "
              f"{q([t for _, _, turns, _ in loaded for n, t in turns if STAGE.get(n) == st])} |")
    print("\n### Extraction span (user -> last variable_extracted) per conversation node")
    print("| node | quiet | loaded |")
    print("|---|---|---|")
    for n in sorted({k for _, _, _, e in recs for k in e}):
        print(f"| {n} | {q([x for _, _, _, e in quiet for x in e.get(n, [])])} | {q([x for _, _, _, e in loaded for x in e.get(n, [])])} |")
    print("\n### Per-call stage totals (sum of visit dwells in stage, seconds)")
    print("| stage | quiet | loaded |")
    print("|---|---|---|")
    for st in ("identity", "account_load", "third_party", "negotiation", "confirm_close"):
        qt, lt = [], []
        for grp, acc in ((quiet, qt), (loaded, lt)):
            for _, dwell, _, _ in grp:
                tot = sum(sum(dwell[n]) for n in dwell if STAGE.get(n) == st)
                if tot:
                    acc.append(tot)
        print(f"| {st} | {q(qt)} | {q(lt)} |")
    print("\n### Per-call turn counts by stage (assistant messages)")
    cnt = collections.defaultdict(lambda: [0, 0])
    for meta, _, turns, _ in recs:
        for n, _ in turns:
            cnt[STAGE.get(n, n)][0 if meta["_call_med"] and meta["_call_med"] <= 6 else 1] += 1
    for st, (a, b) in sorted(cnt.items()):
        print(f"| {st} | quiet {a} | loaded {b} |")


if __name__ == "__main__":
    main()
