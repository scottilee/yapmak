"""Auditor tool: diff an extracted policy IR against a hand-written expected.json (ground truth from the brief).

    .venv/bin/python results/audit/synthetic/diff_ir.py out/<slot>.policy.json results/audit/synthetic/<x>-expected.json

Exit 0 = all compared fields match; 1 = mismatches found. Reports every mismatch with the actual value.
"""
import json, sys


def walk(path, obj):
    cur = obj
    for part in path.split("."):
        if part == "special_cases":
            continue
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
    return cur


def sc_get(policy, name, field):
    for sc in policy.get("special_cases", []):
        if sc.get("name") == name:
            return sc.get(field)
    return "MISSING-CASE"


def norm(v):
    if v is None:
        return None
    if isinstance(v, tuple):
        return list(v)
    return v


def cmp_list_of_dicts(actual, expected, keys):
    out = []
    if not isinstance(actual, list) or len(actual) != len(expected):
        return [f"length {len(actual) if isinstance(actual, list) else 'none'} != {len(expected)}"]
    for i, e in enumerate(expected):
        for k, v in e.items():
            a = norm((actual[i] or {}).get(k))
            if a != v:
                out.append(f"[{i}].{k}: actual={a!r} expected={v!r}")
    return out


def main(policy_path, exp_path):
    policy = json.load(open(policy_path))
    exp = json.load(open(exp_path))
    problems = []
    for path, want in exp.items():
        if path.startswith("special_cases."):
            _, name, field = path.split(".")
            got = norm(sc_get(policy, name, field))
            if got != want:
                problems.append(f"{path}: actual={got!r} expected={want!r}")
            continue
        if path in ("identity.requirements", "bands"):
            got = walk(path, policy)
            sub = cmp_list_of_dicts(got if isinstance(got, list) else [], want, None)
            for s in sub:
                problems.append(f"{path}{s}")
            continue
        got = norm(walk(path, policy))
        if isinstance(want, list) and isinstance(got, list) and path in ("notes.reasons", "calendar.holidays", "phrases.prohibited_before_verification"):
            if sorted(map(str, got)) != sorted(map(str, want)):
                problems.append(f"{path}: actual={got!r} expected={want!r} (as sets)")
            continue
        if got != want:
            problems.append(f"{path}: actual={got!r} expected={want!r}")
    print(f"== {policy_path} vs {exp_path}: {len(problems)} mismatches")
    for p in problems:
        print("  -", p)
    unres = policy.get("unresolved", [])
    print(f"== unresolved entries ({len(unres)}):")
    for u in unres:
        print("  *", json.dumps(u)[:220])
    print("== audit.json (if present):")
    ap = policy_path.replace(".policy.json", ".audit.json")
    try:
        a = json.load(open(ap))
        print("   fixed:", json.dumps(a.get("fixed", []))[:600])
        print("   unresolved:", json.dumps(a.get("unresolved", []))[:600])
    except Exception as e:
        print("   (no audit file:", e, ")")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
