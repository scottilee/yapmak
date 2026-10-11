#!/usr/bin/env python3
"""Read-only workflow comparison; writes only the requested audit report.
Run after the repair owner confirms the export is complete:
.venv/bin/python results/audit/review_final_diff.py
Exit 0: report generated (NOT certification); exit 2: missing/invalid input.
"""
import argparse
import ast
import difflib
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = {
    'cards.list': {'customerNo', 'aiFlow'},
    'cards.balance': {'cardNumber'},
    'contact.email.get': {'customerNo', 'intAddressInfoType'},
    'statement.pdf.send': {'customerNo', 'cardNumber', 'currencyType', 'statementDate', 'emailAddress'},
    'statement.week.get': {'cardNumber'},
    'statement.week.decide': {'cardNumber', 'newStatementWeek', 'statementDay'},
    'statement.week.change': {'cardNumber', 'newStatementWeek', 'statementDay'},
}
BASE = 'https://yapmak-bank-mock.winter-mountain-4405.workers.dev/voice/v1/'


def read(path):
    raw = path.read_bytes()
    obj = json.loads(raw)
    obj = obj.get('workflow', obj)
    if not isinstance(obj.get('nodes'), dict):
        raise ValueError(f'{path}: expected a workflow with a nodes object')
    return obj, hashlib.sha256(raw).hexdigest()


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def objects(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from objects(v)
    elif isinstance(x, list):
        for v in x:
            yield from objects(v)


def pretty(x):
    return json.dumps(x, ensure_ascii=False, indent=2, sort_keys=True)


def diff(a, b):
    return '\n'.join(difflib.unified_diff(pretty(a).splitlines(), pretty(b).splitlines(),
                                       fromfile='v1', tofile='v2', lineterm=''))


def routes(n):
    # Ignore exporter-added null/default metadata; retain operational conditions.
    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()
                    if v is not None and not (k == 'mode' and v == 'exact')}
        if isinstance(x, list):
            return [clean(v) for v in x]
        return x
    return clean({k: n.get(k) for k in ('condition', 'transitions', 'passthrough_default_transition',
        'max_node_turns', 'max_turn_transition', 'excluded_nodes', 'interruptible',
        'return_to_previous_on_interrupt') if n.get(k) is not None})


def apis(w):
    found = {}
    for name, node in w['nodes'].items():
        for i, obj in enumerate(objects(node)):
            fn = obj.get('function', {})
            if fn.get('handler') != '__function__:api_call':
                continue
            props = fn.get('parameters', {}).get('properties', {})
            key = name + '/' + fn.get('name', str(i))
            found[key] = {
                'url': props.get('url', {}).get('default'),
                'method': props.get('method', {}).get('default'),
                'body': props.get('body'),
                'pre_process_code': obj.get('pre_process_code', ''),
                'config': obj.get('config', {}),
            }
    return found


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old', default='results/final-v1/final.workflow.json')
    p.add_argument('--new', default='out/final.workflow.json')
    p.add_argument('--output', default='results/audit/final-v2-diff.md')
    args = p.parse_args()
    oldp, newp, output = [ROOT / x for x in (args.old, args.new, args.output)]
    # The checker must never overwrite workflows or source/pipeline files.
    if output.resolve().parent != (ROOT / 'results/audit').resolve() or output.suffix != '.md':
        p.error('output must be a Markdown report directly under results/audit/')
    try:
        a, ah = read(oldp)
        b, bh = read(newp)
    except (OSError, ValueError) as e:
        p.error(str(e))
    lines = ['# Final v2 workflow diff', '',
        f'Generated {datetime.now(timezone.utc).isoformat()}. Static review only; no calls or simulations.', '',
        f'- Baseline: `{args.old}`; SHA256 `{ah}`.',
        f'- Repaired input: `{args.new}`; SHA256 `{bh}`.',
        '- A generated report is not a passing verdict. Template matches, runtime bodies, routing and speech require the review noted below.', '']
    an, bn = a['nodes'], b['nodes']
    lines += ['## Nodes and routing', '',
        'Added nodes: ' + (', '.join(sorted(bn.keys()-an.keys())) or 'none') + '.',
        'Removed nodes: ' + (', '.join(sorted(an.keys()-bn.keys())) or 'none') + '.',
        f"Entry point: `{a.get('initial_node')}` → `{b.get('initial_node')}`.", '']
    for name in sorted(an.keys() & bn.keys()):
        ar, br = routes(an[name]), routes(bn[name])
        if ar != br:
            at = [x.get('target_node') for x in an[name].get('transitions', [])]
            bt = [x.get('target_node') for x in bn[name].get('transitions', [])]
            lines += [f'- **{name}**: destinations {at} → {bt}. ' +
                      ('The destinations are unchanged; conditions or turn/interrupt handling changed.' if at == bt else 'The possible next steps changed.'),
                      '```diff', diff(ar, br), '```']
    lines += ['', '## Global handling and authored behavior', '']
    ag, bg = a.get('global_nodes', {}), b.get('global_nodes', {})
    for name in sorted(ag.keys() | bg.keys()):
        if name not in ag:
            lines += [f'- **{name}**: new conversation-wide handling.', '```json', pretty(bg[name]), '```']
        elif name not in bg:
            lines += [f'- **{name}**: conversation-wide handling removed.']
        elif ag[name] != bg[name]:
            lines += [f'- **{name}**: trigger, wording or handling changed; inspect the exact differences below.',
                      '```diff', diff(ag[name], bg[name]), '```']
    for key in ('system_prompt', 'test_variables', 'agent_config'):
        if a.get(key) != b.get(key):
            lines += [f'### {key}', '', '```diff', diff(a.get(key), b.get(key)), '```']
    # Includes generated Python, spoken text, recognition schemas and response mappings.
    for name in sorted(an.keys() & bn.keys()):
        fields = ('pre_actions', 'on_enter', 'task_message', 'extraction_schema', 'response_mapping', 'terminal')
        aa = {k: an[name].get(k) for k in fields if an[name].get(k)}
        bb = {k: bn[name].get(k) for k in fields if bn[name].get(k)}
        if aa != bb:
            lines += [f'### Authored behavior: {name}', '', '```diff', diff(aa, bb), '```']
    lines += ['', '## API URLs and request bodies against contract', '',
        'Reference: `hidden/final/sources/documents/2026-10-01-service-contract.md`. Compare both the parameter schema and preprocessing code: preprocessing can replace the actual body.', '']
    ap, bp = apis(a), apis(b)
    seen = set()
    for key in sorted(ap.keys() | bp.keys()):
        if key not in bp:
            lines += [f'- **REVIEW {key}: API call removed.**']; continue
        v = bp[key]
        url = v['url'] or ''
        service = url.removeprefix(BASE)
        seen.add(service)
        body = v.get('body') or {}
        props = body.get('properties', {})
        data = props.get('data', {}).get('properties', {})
        missing = CONTRACT.get(service, set()) - data.keys()
        issues = []
        if service not in CONTRACT: issues.append('URL is not one of the seven contract URLs')
        if v['method'] != 'POST': issues.append('method is not POST')
        if missing: issues.append('missing schema data fields: ' + ', '.join(sorted(missing)))
        if 'ani' not in props.get('call', {}).get('properties', {}): issues.append('call.ani not declared (mock ignores it)')
        changed = key not in ap or any(ap[key].get(k) != v.get(k) for k in ('url', 'method', 'body', 'pre_process_code'))
        lines += [f"- **{key}**: URL/body/preprocessor {'CHANGED' if changed else 'unchanged'}; " +
                  ('REVIEW: ' + '; '.join(issues) if issues else 'schema fields and URL match the contract checks') + '.']
        if changed:
            lines += ['```diff', diff(ap.get(key), v), '```']
    if CONTRACT.keys()-seen:
        lines += ['Missing contract services: ' + ', '.join(sorted(CONTRACT.keys()-seen)) + '.']
    lines += ['', 'Schema checks do not prove runtime substitution or response success handling. Review original cardNumber preservation, current statementDay on both week requests, registered email, issued statementDate, numeric week/day, HTTP status and service result codes. No preprocessing code is executed by this checker.', '',
              '## Dictated-sentence retention', '',
              'Exact literal presence is checked in decoded workflow strings. NOT LITERAL is a review flag, not proof of omission: dynamic templates and Python concatenation must be inspected. Presence in notes/code also does not prove the sentence is reachable or spoken at the right point. Every required checklist row is listed.', '',
              '| ID | v1 | v2 | Required wording |', '|---|---|---|---|']
    checklist = (ROOT/'results/audit/final-dictated-sentences.md').read_text()
    rows = []
    for line in checklist.splitlines():
        m = re.match(r'\|\s*([A-Z]\d+)\b[^|]*\|\s*(.*?)\s*\|', line)
        if not m: m = re.match(r'- (N\d+): (.*)', line)
        if m:
            ident, cell = m.groups()
            snippets = re.findall(r'`([^`]+)`', cell)
            if snippets:
                rows.extend((ident + (f'.{i+1}' if len(snippets) > 1 else ''), text)
                            for i, text in enumerate(snippets))
            else:
                rows.append((ident, cell))
    if not rows:
        p.error('no checklist rows recognized; do not issue an empty sentence report')
    at, bt = '\n'.join(strings(a)), '\n'.join(strings(b))
    def presence(sentence, corpus):
        if sentence == 'wording free': return 'behavioral review'
        if sentence in corpus: return 'literal'
        # Decode Python constants without executing any workflow code.
        constants = []
        for text in corpus.split('\n\n'):
            try:
                constants.extend(n.value for n in ast.walk(ast.parse(text))
                                 if isinstance(n, ast.Constant) and isinstance(n.value, str))
            except (SyntaxError, ValueError): pass
        if sentence in '\n'.join(constants): return 'literal in code'
        return 'NOT LITERAL'
    for ident, sentence in rows:
        lines += [f"| {ident} | {presence(sentence, at)} | {presence(sentence, bt)} | {sentence.replace('|', '/')} |"]
    lines += ['', '## Test-customer data scan', '',
              'Exact-value checks cover customer numbers, full/masked card numbers and email addresses, plus complete customer records. Product names, last-four digits and numeric amounts may coincide with document examples; they are not automatically proof of leakage. Code and prompt differences above still need a human check for customer-specific branches.', '']
    fixture = json.loads((ROOT/'hidden/final/test-environment/test-customers.json').read_text())
    records = fixture['customers']
    literals = set()
    for obj in objects(fixture):
        for key, value in obj.items():
            if key in ('customerNo', 'cardNumber', 'ibanEmail', 'emailAddress') and isinstance(value, str) and value:
                literals.add((key, value))
            if isinstance(key, str) and re.fullmatch(r'[0-9*]{12,19}', key): literals.add(('card map key', key))
    hits = [(k, v) for k, v in sorted(literals) if v in bt]
    lines += [f'Exact identifier hits: **{len(hits)}**.']
    for k,v in hits: lines += [f'- REVIEW `{k}`: `{v}`.']
    whole = sum(pretty(record) in pretty(b) for record in records)
    lines += [f'Complete serialized customer-record matches: {whole}.', '',
              '## Operator sign-off', '',
              '- [ ] Repair owner confirmed this is the completed export, not an intermediate file.',
              '- [ ] Every changed routing/global rule agrees with the latest email decisions.',
              '- [ ] Every NOT LITERAL sentence was located in an assembled template or recorded as a defect.',
              '- [ ] Changed API preprocessing preserves the contract; success checks are correct.',
              '- [ ] No fixture-specific answers or branches were introduced.',
              '- [ ] Required live checks pass; static comparison is not a substitute.', '']
    # Detect concurrent replacement instead of silently reporting stale files.
    if hashlib.sha256(newp.read_bytes()).hexdigest() != bh:
        p.error('new workflow changed during review; rerun after repair completes')
    output.write_text('\n'.join(lines))
    print(f'Wrote {output.relative_to(ROOT)}; {len(rows)} sentence rows, {len(bp)} API calls, {len(hits)} identifier hits. Manual sign-off required.')

if __name__ == '__main__':
    main()
