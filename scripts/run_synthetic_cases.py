"""Official case runner with explicit synthetic now override; no fault injection.

python scripts/run_synthetic_cases.py AGENT_ID --cases tests/fixtures/synthetic/next_friday_from_friday.json --out results/friday.json
This command starts a simulation. Coordinate the single workspace slot first.
"""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import run_cases


def load_cases(path):
    cases = json.loads(Path(path).read_text())
    public = {c['id']: c for c in json.loads((ROOT / 'public-test-set.json').read_text())}
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Use one script per existing case ID per run; run variant files separately.')
    for case in cases:
        base = public[case['id']]
        if case['identity'] != base['identity'] or case['products'] != base['products']:
            raise ValueError('The practice mock cannot accept edited identity/products via this runner.')
        if case.get('faults', []) != base.get('faults', []):
            raise ValueError('Custom fault injection is unsupported by the documented practice API.')
    return cases


if __name__ == '__main__':
    if '--cases' not in sys.argv:
        raise SystemExit('Supply --cases PATH; see module usage.')
    cases = load_cases(sys.argv[sys.argv.index('--cases') + 1])
    by_id = {c['id']: c for c in cases}
    original_http = run_cases.http
    def http(path, body=None):
        result = original_http(path, body)
        if path == '/v1/practice/sessions' and body and body.get('case') in by_id:
            now = by_id[body['case']].get('variables', {}).get('now')
            if now:
                result['variables']['now'] = now
        return result
    run_cases.http = http
    run_cases.main()
