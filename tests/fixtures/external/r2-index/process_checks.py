"""Read-only, local process audits. Never runs a build, extraction, simulation or API call.

.venv/bin/python -B tests/fixtures/external/r2-index/process_checks.py traces traces/
.venv/bin/python -B tests/fixtures/external/r2-index/process_checks.py build-output BUILD_STDOUT

Outputs only finding locations/categories for secrets, never matched secret values.
Pattern scanning is a heuristic, not proof that a trace contains no credentials.
"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
PATTERNS = (
    ("provider_key", re.compile(r"\b(?:sk-(?:proj-|ant-|svcacct-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("bearer", re.compile(r"\bBearer\s+([A-Za-z0-9._~+/=-]{12,})", re.I)),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("credential_assignment", re.compile(r'''["']?(?:[a-z0-9_-]*api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization)["']?\s*[:=]\s*["']?([^\s"',;}\\]{8,})''', re.I)),
)
PLACEHOLDER = re.compile(r"^(?:\$|\{|<)|placeholder|redacted|example|dummy|changeme|your[_-]", re.I)


def scan_tree(root):
    if not root.is_dir():
        return {"error": "trace directory missing", "files_scanned": 0}, 2
    findings, failures = [], []
    count = 0
    # Include every regular file recursively, independent of extension; do not print lines.
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        count += 1
        try:
            data = path.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            failures.append(str(path.relative_to(root)))
            continue
        for lineno, line in enumerate(data.splitlines(), 1):
            for category, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    candidate = match.group(1) if match.lastindex else match.group(0)
                    if not PLACEHOLDER.search(candidate):
                        findings.append({"file": str(path.relative_to(root)), "line": lineno, "category": category})
                        break
    return {"files_scanned": count, "findings": findings, "unreadable_files": failures,
            "scope": "all regular files under the supplied trace directory",
            "limitation": "Heuristic candidate detection; unknown credential formats may not match. Review candidates privately; never paste values."}, 2 if failures or not count else int(bool(findings))


def final_build_result(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"error": "build output missing or unreadable"}, 2
    decoder = json.JSONDecoder()
    candidates = []
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        # Final printed build payload has these keys; a trace run_end is not enough.
        if isinstance(value, dict) and all(k in value for k in ("slot", "workflow", "trace")):
            candidates.append(value)
    if not candidates:
        return {"error": "no printed final build-result object found"}, 2
    result = candidates[-1]
    if "degraded" not in result:
        return {"error": "final build result omits degraded"}, 2
    degraded = result["degraded"]
    if not isinstance(degraded, list):
        return {"error": "degraded is not an array"}, 2
    if any(not isinstance(v, str) for v in degraded):
        return {"error": "degraded contains non-string entries"}, 2
    # Do not echo raw diagnostics: they may contain quoted request bodies or secrets.
    return {"final_result_found": True, "degraded_present": True,
            "degraded_count": len(degraded), "degraded_empty": not degraded,
            "next_step": "Review original diagnostics locally; nonempty degraded is not a clean build." if degraded else "Check process exit code and policy/API results separately; empty degraded alone is not proof of correctness."}, int(bool(degraded))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("traces").add_argument("directory", type=Path)
    sub.add_parser("build-output").add_argument("stdout_file", type=Path)
    args = ap.parse_args()
    report, status = scan_tree(args.directory) if args.command == "traces" else final_build_result(args.stdout_file)
    print(json.dumps(report, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
