"""Read-only oracle comparison, no extraction or live calls.
Usage: .venv/bin/python -B tests/fixtures/external/compare_expected.py PACKAGE_DIR POLICY_JSON
Prints all mismatches and unresolved rules; returns nonzero if either is present.
"""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from check_synthetic_ir import project, unknown_keys
import policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("policy_json", type=Path)
    args = parser.parse_args()
    oracle = json.loads((args.package / "expected.json").read_text())
    raw = json.loads(args.policy_json.read_text())
    normalized = json.loads(policy.PolicyIR.from_dict(raw).to_json())
    mismatches = []
    for path, item in oracle["checks"].items():
        want = item["expected"]
        try:
            actual = project(normalized, path)
        except (KeyError, IndexError, StopIteration, TypeError):
            actual = {"missing": True}
        if path == "outcomes.$table":
            want = {k: sorted(v) for k, v in want.items()}
        if path in ("calendar.holidays", "notes.reasons", "phrases.prohibited_before_verification"):
            want = sorted(want)
            if isinstance(actual, list):
                actual = sorted(actual)
        if actual != want:
            mismatches.append(dict(path=path, expected=want, actual=actual, source=item["source"]))
    errors = policy.validate(policy.PolicyIR.from_dict(raw))
    unknown = unknown_keys(raw, normalized)
    unresolved = normalized.get("unresolved", [])
    print(json.dumps(dict(fixture=oracle["fixture"], checks=len(oracle["checks"]),
                         mismatches=mismatches, unresolved=unresolved,
                         structural_errors=errors, unknown_keys=unknown), indent=2))
    return int(bool(mismatches or unresolved or errors or unknown))


if __name__ == "__main__":
    raise SystemExit(main())
