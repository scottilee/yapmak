"""Speech-to-structure functional chats on the reused runtime-check slot. No simulations."""
import argparse
import datetime
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import freya
from scripts.chatlib import Chat
from runtime_checks import publish, save_json, variables_from, conversation, route, code_node

FIXTURE = ROOT / 'tests/fixtures/extraction_schemas.json'
COMMON = '''Extract only facts expressed by the caller. Do not invent a date, amount, or confirmation from an agent offer. The latest correction replaces the earlier value. Incomplete fragments remain partial until the caller finishes. Only combine fragments across turns when the previous answer was explicitly partial. Ignore unrelated dates in stories. Use zero for an unspecified integer; omit an unspecified optional string. These rules override built-in calendar interpretation: never convert a relative weekday or vague period to a concrete date.\n{{extractor.type_preamble}}\nVariables:\n{{extractor.variables_list}}\nRecent conversation:\n{{extractor.conversation.last-10}}\nCurrent speech:\n{{extractor.speech}}'''


def field(name, typ, description, enum=None, pattern=None):
    value = dict(name=name, type=typ, description=description, min_confidence=0.7, extraction_prompt=COMMON)
    if enum:
        value['enum_values'] = enum
    if pattern:
        value['validation_pattern'] = pattern
    return value


def make_fixture():
    schemas = {}
    schemas['date'] = [
        field('date_status', 'string', 'For the current payment-date answer: complete if an exact date expression is finished; vague for an indefinite period; partial if the caller explicitly pauses before completing it; absent if no payment date answer.', ['complete', 'vague', 'partial', 'absent']),
        field('date_kind', 'string', 'Shape of latest corrected payment date: keyword for today/tomorrow/vague; weekday for ONLY this/next weekday without a numbered day; numbered if a day number is supplied, even with an incidental weekday such as Monday the 26th; none for partial/absent.', ['keyword', 'weekday', 'numbered', 'none']),
        field('date_keyword', 'string', 'Only the literal relative meaning today, tomorrow, or vague (including next week, week after next, salary time, end of month). Do not manufacture a concrete date.', ['today', 'tomorrow', 'vague']),
        field('date_weekday', 'string', 'Weekday named in a weekday-only expression.', ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']),
        field('date_relative', 'string', 'Literal this or next qualifier for a weekday-only expression.', ['this', 'next']),
        field('date_day', 'integer', 'Corrected explicit day of month, including spoken ordinals; 0 if not supplied. The 21st, sorry, the 20th means 20.'),
        field('date_month', 'integer', 'Explicit month as 1..12; 0 if not stated. Never infer from system date.'),
        field('date_year', 'integer', 'Four-digit year only if explicitly spoken; otherwise 0. Never use system year.'),
        field('customer_intent', 'string', 'Intent of latest relevant speech. A proposed amount/date is proposal, not refusal. A question is question, not confirmation.', ['proposal', 'refusal', 'question', 'hardship', 'dispute', 'paid', 'restructure', 'human', 'other'])]
    schemas['amount'] = [
        field('amount_status', 'string', 'complete only if caller finished the amount; partial for trailing fragments or an explicit pause; absent otherwise. Combine a continuation only with the immediately preceding partial amount.', ['complete', 'partial', 'absent']),
        field('amount_value', 'float', 'Latest fully spoken corrected payment amount as a decimal number. Four hundred and twenty = 420. A trailing four hundred and... is incomplete and must not count as 400. Omit while partial.')]
    schemas['identity_date'] = [
        field('identity_status', 'string', 'complete if entire birth day, month and full year have been supplied; partial if unfinished; absent if unrelated.', ['complete', 'partial', 'absent']),
        field('identity_date_text', 'string', 'Transcribe ONLY the birth date answer; preserve spoken component order and numeric ambiguity. Convert word-number components to digits if needed but never swap day/month yourself. A date fragment is not a full date.')]
    schemas['identity_digits'] = [
        field('identity_status', 'string', 'complete only once all four phone digits have been supplied. partial for two digits and a pause. Combine only the current unfinished answer, never earlier wrong answers.', ['complete', 'partial', 'absent']),
        field('identity_digits', 'string', 'Exactly the four phone digits supplied, preserving leading zero. Convert digit words; omit if fewer than four have been supplied.', pattern='^[0-9]{4}$')]
    schemas['consent'] = [
        field('consent_action', 'string', 'Current response to read-back: confirm ONLY an unqualified clear yes to the unchanged proposal. Any amount/date correction is correct even when preceded by yes. No is refuse. Questions, silence or unrelated speech are pending.', ['confirm', 'correct', 'refuse', 'pending']),
        field('corrected_amount', 'float', 'New amount explicitly requested in the latest correction; omit when no amount correction. Never copy the old read-back amount.')]
    schemas['consent'][1]['min_confidence'] = 0.5
    result = dict(version=1, status='candidate', contract=dict(
        completeness='Gate on the per-turn status AND code validity; never on an is_set number alone.',
        dates='Only date_kind selects which fields are consumed. Ignore stale irrelevant fields; year/month zero means unspecified.',
        consent='Reset consent_action and corrected_amount after processing. Revision change invalidates prior confirmation.',
        prompts='Every custom extraction_prompt includes all four required extractor placeholders.',
        confidence='0.7 for fields except corrected_amount=0.5: observed correct 350 rejected at confidence 0.562. Validate numeric corrections in code; missing extraction cannot authorize an action.'), schemas=schemas)
    FIXTURE.write_text(json.dumps(result, indent=2))
    return result


def capture(ids, variables, messages, out, label):
    records = []
    def cleanup(error):
        save_json(out / (label + '.end-error.json'), {'error': str(error)})
    with Chat(ids['workflow_id'], variables, on_cleanup_error=cleanup) as session:
        try:
            for speech in messages:
                response = session.send(speech)
                call = session.evidence()
                values, events = variables_from(call)
                save_json(out / (label + '.call.json'), call)
                records.append(dict(speech=speech, response=response.get('response'), values=values,
                                    routes=[dict(source=e.get('from_node'), target=e.get('target'), reason=e.get('reason')) for e in events if e.get('matched')]))
                save_json(out / (label + '.turns.json'), records)
            return records
        except Exception as exc:
            save_json(out / (label + '.error.json'), dict(error=str(exc), call_id=session.call_id, completed_turns=len(records)))
            raise


def source_adapter(mode):
    source = (ROOT / 'bankcal.py').read_text()
    if mode == 'date':
        adapter = '''
vars['date_ready'] = 'no'
vars['date_process_count'] = int(vars.get('date_process_count', 0)) + 1
try:
    kind = str(vars.get('date_kind', ''))
    expr = dict()
    if kind == 'keyword':
        expr['keyword'] = str(vars.get('date_keyword', ''))
    elif kind == 'weekday':
        expr['weekday'] = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].index(str(vars.get('date_weekday', '')))
        expr['relative'] = str(vars.get('date_relative', ''))
    elif kind == 'numbered':
        for part in ('day','month','year'):
            n = int(vars.get('date_' + part, 0) or 0)
            if n:
                expr[part] = n
    calendar = dict(next_weekday_means_following_week=True, missing_date_parts='next_occurrence')
    now = parse_now(str(vars.get('now', '')))
    resolved = resolve_date_expr(now[0], expr, calendar) if now else None
    vars['date_resolved'] = resolved or 'unreadable'
    vars['date_expr_json'] = json.dumps(expr)
    vars['date_ready'] = 'yes' if resolved and resolved != 'vague' else 'no'
except Exception:
    vars['date_resolved'] = 'unreadable'
'''
    elif mode == 'amount':
        adapter = "\nvars['amount_process_count'] = int(vars.get('amount_process_count', 0)) + 1\nvars['amount_normalized'] = str(vars.get('amount_value', 'missing'))\n"
    elif mode == 'identity_date':
        adapter = "\nvars['identity_process_count'] = int(vars.get('identity_process_count', 0)) + 1\nvars['identity_normalized'] = normalize_date_answer(str(vars.get('identity_date_text', '')), 'dmy') or 'unreadable'\n"
    elif mode == 'identity_digits':
        adapter = "\nvars['identity_process_count'] = int(vars.get('identity_process_count', 0)) + 1\nvars['identity_normalized'] = normalize_digits(str(vars.get('identity_digits', '')), 4) or 'unreadable'\n"
    else:
        adapter = '''
vars['consent_process_count'] = int(vars.get('consent_process_count', 0)) + 1
try:
    action = str(vars.get('consent_action', ''))
    revision = int(vars.get('proposal_revision', 1))
    if action == 'correct':
        vars['proposal_revision'] = revision + 1
        vars['confirmed_revision'] = 0
        vars['consent_valid'] = 'false'
        vars['proposal_complete'] = 'false'
        amount = vars.get('corrected_amount')
        if amount not in (None, ''):
            number = float(amount)
            if 0 <= number < float('inf'):
                vars['proposed_amount'] = number
                vars['proposal_complete'] = 'true'
    elif action == 'confirm' and str(vars.get('proposal_complete', 'false')) == 'true':
        vars['confirmed_revision'] = revision
        vars['consent_valid'] = 'true'
    else:
        vars['confirmed_revision'] = 0
        vars['consent_valid'] = 'false'
except Exception:
    vars['consent_valid'] = 'false'
vars['consent_action'] = 'pending'
vars['corrected_amount'] = -1
'''
    reset = ''
    if mode == 'date':
        reset = "\nvars['date_status'] = 'absent'\nvars['date_kind'] = 'none'\nfor key in ('date_day','date_month','date_year'):\n    vars[key] = 0\nfor key in ('date_keyword','date_weekday','date_relative'):\n    vars[key] = ''\n"
    elif mode == 'amount':
        reset = "\nvars['amount_status'] = 'absent'\nvars['amount_value'] = -1\n"
    elif mode.startswith('identity'):
        reset = "\nvars['identity_status'] = 'absent'\nvars['identity_date_text'] = 'unresolved'\nvars['identity_digits'] = 'unresolved'\n"
    return source + adapter + reset


def workflow(mode, schema):
    settings = {
        'date': ('date_status', ['complete', 'vague'], 'Ask for the exact payment day. If vague, ask for the exact day. If incomplete, ask the caller to finish. Never guess. Current resolved date is {{date_resolved}}.'),
        'amount': ('amount_status', ['complete'], 'Ask what payment amount the caller is proposing for this extraction check. If incomplete ask them to finish; do not guess.'),
        'identity_date': ('identity_status', ['complete'], 'Ask for date of birth, then wait for the complete day, month and year. Do not invent missing components.'),
        'identity_digits': ('identity_status', ['complete'], 'Ask for the last four phone digits. If fewer are given, ask for the remaining digits; never fill them yourself.'),
        'consent': ('consent_action', ['confirm', 'correct', 'refuse'], 'Read back: credit card, {{proposed_amount}} dollars on 16 October 2026. Ask Do you confirm? After a correction read back the revised amount and ask again. If proposal_complete is false, ask the caller to repeat the corrected amount instead of confirming the old amount. Proposal complete: {{proposal_complete}}. Answer questions without assuming consent.')}
    variable, values, prompt = settings[mode]
    transitions = [route('check', variable, v) for v in values]
    if mode == 'date':
        for transition in transitions:
            transition['condition'] = dict(logic='and', conditions=[transition['condition'], dict(variable='customer_intent', operator='equals', operand='proposal')])
    check = code_node(source_adapter(mode), [route('collect')])
    nodes = dict(collect=conversation('collect', prompt, schema, transitions), check=check)
    return dict(initial_node='collect', system_prompt='You are a synthetic functional test assistant. Speak English in short sentences. Do not call any bank API.', nodes=nodes)


CASES = {
    'date': [
        ('pub04', ['Hello.', 'I can pay on 6 November.'], ['2026-11-06']),
        ('pub07', ['Hello.', 'The week after next.', 'Monday the 26th.'], ['vague', '2026-10-26']),
        ('pub13', ['Hello.', '30 October.'], ['2026-10-30']),
        ('in_words', ['Hello.', 'The thirtieth of October.'], ['2026-10-30']),
        ('corrects', ['Hello.', 'The 21st, sorry, I mean the 20th.'], ['2026-10-20']),
        ('pieces', ['Hello.', 'The twenty...', '...third of October.'], [None, '2026-10-23']),
        ('relative', ['Hello.', 'Next Friday.'], ['2026-10-23']),
        ('stale_partial', ['Hello.', '6 November.', 'Actually change that to the twenty...', '...third of October.'], ['2026-11-06', None, '2026-10-23']),
        ('intents', ['Hello.', 'I will not pay anything.', 'I lost my job.', 'This debt is not mine.', 'I already paid.', 'I need lower instalments.', 'I want a human.', 'Why do you need that?'], [None] * 7)],
    'amount': [('words', ['Hello.', 'Four hundred and twenty.'], ['420']),
               ('pieces', ['Hello.', 'Four hundred and...', '...twenty.'], [None, '420']),
               ('corrects', ['Hello.', 'Four hundred, sorry, three hundred and fifty.'], ['350']),
               ('stale_partial', ['Hello.', 'Three hundred.', 'Actually four hundred and...', '...twenty.'], ['300', None, '420'])],
    'identity_date': [('words', ['Hello.', 'Fourteenth of March nineteen eighty-eight.'], ['1988-03-14']),
                      ('numeric', ['Hello.', '03/06/1987.'], ['1987-06-03']),
                      ('pieces', ['Hello.', 'Fourteenth of March...', '...nineteen eighty-eight.'], [None, '1988-03-14'])],
    'identity_digits': [('words', ['Hello.', 'Zero three five eight.'], ['0358']),
                        ('pieces', ['Hello.', 'Forty-four...', '...seventy-one.'], [None, '4471'])],
    'consent': [('confirm', ['Hello.', 'Yes, I confirm.'], ['true']),
                ('correct', ['Hello.', 'Yes, but make that three hundred and fifty instead.'], ['false']),
                ('revision', ['Hello.', 'Yes, I confirm.', 'Actually change the amount to three hundred and fifty.', 'Yes, I confirm the new amount.'], ['true', 'false', 'true']),
                ('refuse', ['Hello.', 'No, I do not agree.'], ['false']),
                ('question', ['Hello.', 'Which card is this?'], [None])]
}


def run(mode, fixture, out):
    ids = publish(workflow(mode, fixture['schemas'][mode]), out)
    result_key = {'date': 'date_resolved', 'amount': 'amount_normalized', 'identity_date': 'identity_normalized', 'identity_digits': 'identity_normalized', 'consent': 'consent_valid'}[mode]
    count_key = ('identity' if mode.startswith('identity') else mode) + '_process_count'
    report = {}
    for label, messages, expected in CASES[mode]:
        records = capture(ids, dict(now='2026-10-14T11:00', date_resolved='unset', proposed_amount=420, proposal_revision=1, confirmed_revision=0, consent_valid='false', proposal_complete='true'), messages, out, label)
        checks = []
        previous = int(records[0]['values'].get(count_key, 0) or 0)
        for record, target in zip(records[1:], expected):
            values = record['values']; actual = values.get(result_key)
            count = int(values.get(count_key, 0) or 0)
            if target is None:
                passed = count == previous
            elif mode == 'amount':
                passed = actual is not None and float(actual) == float(target) and count > previous
            else:
                passed = str(actual) == target and count > previous
            if label == 'intents':
                expected_intent = {'I will not pay anything.': 'refusal', 'I lost my job.': 'hardship', 'This debt is not mine.': 'dispute', 'I already paid.': 'paid', 'I need lower instalments.': 'restructure', 'I want a human.': 'human', 'Why do you need that?': 'question'}[record['speech']]
                passed = passed and values.get('customer_intent') == expected_intent
            if mode == 'consent' and target == 'false' and (label == 'correct' or 'change' in record['speech'].lower()):
                passed = passed and int(values.get('confirmed_revision', -1)) == 0 and float(values.get('proposed_amount', 0)) == 350
            checks.append(dict(speech=record['speech'], expected=target, actual=actual, process_count=count, previous_count=previous, passed=passed,
                               extracted={k:v for k,v in values.items() if k.startswith(('date_', 'amount_', 'identity_', 'consent_', 'proposal_', 'confirmed_', 'proposed_', 'customer_intent'))}))
            previous = count
        report[label] = dict(passed=all(c['passed'] for c in checks), checks=checks)
        save_json(out / 'summary.json', report)
        print(mode, label, 'PASS' if report[label]['passed'] else 'FAIL', json.dumps(checks), flush=True)
    return report


if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--only'); ap.add_argument('mode', choices=['init', 'date', 'amount', 'identity_date', 'identity_digits', 'consent']); a=ap.parse_args()
    fixture = make_fixture() if a.mode == 'init' or not FIXTURE.exists() else json.loads(FIXTURE.read_text())
    if a.mode != 'init':
        out = ROOT / 'results/baseline' / ('extraction-' + a.mode + '-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        out.mkdir(parents=True)
        print('Artifacts:', out, flush=True)
        if a.only:
            CASES[a.mode] = [case for case in CASES[a.mode] if case[0] == a.only]
            if not CASES[a.mode]:
                raise SystemExit('Unknown case label')
        run(a.mode, fixture, out)
