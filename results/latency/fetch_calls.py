"""Auditor tool: fetch get_call transcripts for sampled simulation calls (READ-ONLY; no simulations, no writes).

Samples call_ids from results/gen/*.json across time windows and agent versions, fetches each transcript
serially, caches under results/audit/latency/calls/. Re-runnable; cached files are skipped.

    source .env; .venv/bin/python results/audit/latency/fetch_calls.py
"""
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent / "calls"
OUT.mkdir(parents=True, exist_ok=True)

# file -> (max calls to sample, window label) — spans quiet/loaded windows and agent versions v8..v13
PLAN = [
    ("a-run1.json", 10, "loaded-early"), ("a-run3.json", 10, "quiet-early"),
    ("a-run4.json", 10, "quiet-early"), ("a-pieces2.json", 10, "quiet-mid"),
    ("a-talkative1.json", 10, "mid"), ("a-corrects3.json", 10, "mid"),
    ("a-reps3.json", 10, "loaded-late-v10"), ("a-reps3-v11.json", 10, "loaded-late-v11"),
    ("a-v13.json", 10, "loaded-late-v13"), ("a-asksback-v13.json", 10, "loaded-late-v13"),
    ("b-reps3.json", 3, "loaded-late-v10"), ("b-v12.json", 3, "loaded-late-v12"),
    ("b-run2.json", 3, "quiet-early"), ("cal-friday-next-friday.json", 3, "calendar-window"),
    ("cal-holiday-today-deadline.json", 3, "calendar-window"),
]


def rows_of(d):
    rows = []
    for src in (d.get("all_rows") or [], [d.get("rows") or []]):
        for item in src:
            if isinstance(item, list):
                rows += item
            elif isinstance(item, dict):
                rows.append(item)
    seen, out = set(), []
    for r in rows:
        cid = r.get("call_id")
        if cid and cid not in seen:
            seen.add(cid); out.append(r)
    return out


def main():
    todo = []
    for fname, n, label in PLAN:
        p = ROOT / "results" / "gen" / fname
        if not p.exists():
            continue
        d = json.load(open(p))
        for r in rows_of(d)[:n]:
            todo.append((fname, label, r["call_id"], r.get("id"), r.get("slowest_turn_s"), r.get("ended")))
    print(f"planned fetches: {len(todo)}")
    got = cached = fail = 0
    for fname, label, cid, case, slow, ended in todo:
        dest = OUT / f"{cid}.json"
        meta = OUT / f"{cid}.meta.json"
        if not meta.exists():
            meta.write_text(json.dumps({"file": fname, "window": label, "case": case, "slowest_turn_s": slow, "ended": ended}))
        if dest.exists():
            cached += 1
            continue
        try:
            call = freya.get_call(cid)
            dest.write_text(json.dumps(call))
            got += 1
            time.sleep(0.2)
        except Exception as e:
            fail += 1
            print("FETCH FAIL", cid, repr(e)[:120])
    print(f"fetched={got} cached={cached} failed={fail}")


if __name__ == "__main__":
    main()
