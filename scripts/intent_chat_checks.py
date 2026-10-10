"""Serial, isolated chat-only probes of the compiler's unmodified intent schemas.

No simulations and no bank tools. Reuses runtime-check. Results are checkpointed
after every case; --limit supports a pilot and --resume continues the same snapshot.
"""
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import freya
import policy
from runtime_checks import publish, save_json, variables_from


# Six semantic variants per value, each exercised in five speech styles.
NEG = {
    'accepts': ['Yes, that works for me.', 'Okay, I agree to your offer.', 'I can do the payment you suggested.', 'Yes, Friday the sixteenth works.', 'Agreed, four hundred and twenty on the sixteenth of October.', 'That amount on that date is fine.'],
    'pays_today': ['I can pay today.', 'I will pay it now.', 'I can clear it this afternoon.', 'I will send the payment today.', 'I can make the payment before today ends.', 'I am able to pay right now.'],
    'proposes': ['I can pay on the twentieth of October.', 'I could do two hundred.', 'How about three hundred on Monday the nineteenth?', 'The week after next would suit me.', 'I could pay on the thirtieth of October.', 'I can offer three hundred and fifty instead.'],
    'refuses': ['No, I cannot pay.', 'I will not make a payment.', 'I have nothing available to pay.', 'No payment is possible.', 'I cannot agree to paying anything.', 'There is no money I can pay.'],
    'too_much': ['That full amount is too much.', 'Could you suggest a smaller amount?', 'You tell me what is the lowest I can pay.', 'That is more than I can afford; offer me something lower.', 'Can you lower the amount?', 'I need a lower amount, but you tell me what it is.'],
    'already_paid': ['I already paid this bill.', 'I sent the payment yesterday.', 'That overdue amount has already been paid.', 'I paid this balance earlier this week.', 'I have already made the payment you are asking for.', 'I transferred the money for this debt already.'],
    'dispute': ['This debt is not mine.', 'I never had that credit card.', 'That account was closed years ago.', 'I paid off and closed that product long ago.', 'You have the wrong debt attached to me.', 'I dispute that I owe this money.'],
    'hardship': ['I lost my job.', 'I am seriously ill.', 'My husband has just died.', 'I was made redundant.', 'I am in hospital with an illness.', 'There has been a death in my family.'],
    'restructuring': ['I need a payment plan.', 'Can you reduce my monthly instalments?', 'I want to restructure the debt.', 'Could I spread repayment over several months?', 'I need lower instalments going forward.', 'Can we arrange an instalment plan?'],
    'human': ['I want to speak to a human.', 'Please put me through to a person.', 'Can I talk to a live agent?', 'Connect me with a colleague.', 'I would rather discuss this with a human adviser.', 'Transfer me to a member of staff.'],
    'scam': ['Is this a scam?', 'How do I know this is not a scam?', 'Are you trying to defraud me?', 'Is this call fraudulent?', 'Could this be a fake bank call?', 'How can I tell you are not a scammer?'],
    'refuses_to_talk': ['I do not want to talk.', 'End this call.', 'Stop talking to me.', 'I refuse to discuss anything with you.', 'Please hang up now.', 'I am not willing to have this conversation.'],
    'question': ['What happens after I pay?', 'Which account are you talking about?', 'Will you send me a text message?', 'Why is this amount overdue?', 'You tell me what this call is about.', 'What do you mean by overdue?'],
    'other': ['Hello.', 'I can hear you.', 'One moment, please.', 'There is a lot of noise here.', 'I have just opened the door.', 'The weather is wet today.'],
}
HOLDER = {
    'confirmed': ['Yes, speaking.', 'That is me.', 'Yes, I am Alex Morgan.', 'You are speaking to Alex Morgan.', 'Alex Morgan here.', 'Yes, this is Alex.'],
    'third_party': ['I am his wife.', 'This is his colleague.', 'Alex is not here.', 'You are speaking with his brother.', 'I am a friend, not Alex.', 'He is away from the phone.'],
    'wrong_number': ['You have the wrong number.', 'This is not his phone number.', 'No Alex Morgan has this number.', 'You have dialled an incorrect number.', 'He does not own this number.', 'This number belongs to someone else.'],
    'deceased': ['Alex has died.', 'He passed away.', 'Mr Morgan is deceased.', 'We lost Alex last month; he died.', 'Alex is no longer alive.', 'He sadly passed away recently.'],
    'wants_human': NEG['human'],
    'refuses': NEG['refuses_to_talk'],
    'unclear': ['Hello.', 'Go ahead.', 'Who is this?', 'What is this about?', 'Can you hear me?', 'Why are you calling?'],
}
IDENTITY = {
    'answers': ['The four digits are one two three four.', 'One two three four.', 'They end in zero three five eight.', 'The last four are four four seven one.', 'My phone ends in nine eight seven six.', 'Zero zero one two.'],
    'declines': ['I will not give those digits.', 'I do not want to answer that security question.', 'I refuse to share that information.', 'I am not providing personal information.', 'No, I will not answer the question.', 'I am unwilling to supply the phone digits.'],
    'asks_purpose': ['What is this call about?', 'Why are you calling me?', 'Tell me the purpose of the call first.', 'What do you want to discuss?', 'Why has the bank contacted me?', 'Before I answer, what is the reason for this call?'],
    'wants_human': NEG['human'],
    'refuses_to_talk': NEG['refuses_to_talk'],
    'other': ['Are you a robot?', 'Is this a scam?', 'How can I check this is really the bank?', 'Can you repeat the question?', 'I cannot hear you clearly.', 'Are you an automated assistant?'],
}
CALLBACK = {
    'gives_time': ['Tomorrow around eleven in the morning.', 'Tomorrow morning.', 'He is available today at three in the afternoon.', 'Try Friday at ten.', 'Around eleven.', 'Tomorrow.'],
    'wrong_number': HOLDER['wrong_number'],
    'deceased': HOLDER['deceased'],
    'cannot_say': ['I do not know when he will be back.', 'I cannot say when he is available.', 'I have no idea when you can reach him.', 'His schedule is unknown to me.', 'I cannot give you a day or a time.', 'I am not sure when he will return.'],
    'refuses': ['I will not help arrange a call.', 'I refuse to tell you when he is available.', 'I do not want to help you reach him.', 'I will not give you a callback time.', 'No, I am unwilling to arrange that.', 'I refuse to pass on any message or help.'],
    'asks_purpose': ['What is this call about?', 'Why do you need to speak to him?', 'What do you want from Alex?', 'What is the purpose of the call?', 'Why are you calling him?', 'Tell me what this concerns.'],
    'other': ['Hello.', 'Please repeat that.', 'The line is noisy.', 'I am just opening the door.', 'I can hear you now.', 'One moment, please.'],
}
READBACK = {
    'confirms': ['Yes, I confirm.', 'That is correct.', 'Yes, four hundred and twenty on the sixteenth of October.', 'I confirm the amount and date you read back.', 'Yes, please proceed with that promise.', 'Correct, Friday the sixteenth.'],
    'changes': ['Actually make it three hundred and fifty.', 'Yes, but change the date to the twentieth.', 'No, I meant the thirtieth of October.', 'Change the amount to four hundred.', 'Use Monday the nineteenth instead.', 'I need to change that to two hundred on the twentieth.'],
    'declines': ['No, I do not confirm.', 'I withdraw my agreement.', 'Do not proceed with that promise.', 'No, that is not agreed.', 'I am not authorizing this.', 'I do not accept the read-back.'],
    **{k: NEG[k] for k in ('already_paid', 'dispute', 'hardship', 'restructuring', 'human', 'refuses_to_talk', 'question', 'other')},
}
GROUPS = {'negotiate': ('cust_intent', NEG), 'opening': ('holder', HOLDER), 'third_party': ('tp_intent', CALLBACK), 'identity': ('id_intent', IDENTITY), 'readback': ('rb_intent', READBACK)}
STYLES = ('in_words', 'pieces', 'corrects', 'talkative', 'asks_back')
CONTEXT = {
    'negotiate': 'Can you pay four hundred and twenty on Friday the sixteenth of October?',
    'opening': 'Am I speaking with Alex Morgan?',
    'third_party': 'Which day and what time can Alex Morgan be reached?',
    'identity': 'Please tell me the last four digits of your phone number.',
    'readback': 'For the credit card, four hundred and twenty on Friday the sixteenth of October 2026. Do you confirm?',
}


def corpus():
    cases = []
    for group, (variable, intents) in GROUPS.items():
        # Interleave values so a stopped run still has broad coverage.
        for style in STYLES:
            for i in range(6):
                for intent, phrases in intents.items():
                    phrase = phrases[i]
                    if style == 'pieces':
                        # A real two-turn delivery. Final interpretation must use the
                        # unfinished answer, rather than importing unrelated history.
                        words = phrase.split()
                        cut = max(1, len(words) // 2)
                        turns = [' '.join(words[:cut]) + ' ...', '... ' + ' '.join(words[cut:])] if len(words) > 1 else ['Let me think ...', phrase]
                    elif style == 'corrects':
                        turns = ['Sorry, let me say that clearly: ' + phrase]
                    elif style == 'talkative':
                        turns = ['I was just getting settled and there is a bit of noise here. ' + phrase + ' That is what I wanted to say.']
                    elif style == 'asks_back':
                        turns = ['Can you hear me clearly? ' + phrase]
                    else:
                        turns = [phrase]
                    cases.append(dict(id=f'{group}-{intent}-{style}-{i+1}', group=group, variable=variable,
                                      expected=intent, style=style, turns=turns, ambiguity='mixed_question' if style == 'asks_back' and intent not in ('question','unclear','other','asks_purpose','scam') else None))
    # Explicit boundary controls, including genuinely changed intent and callback parts.
    extras = [
        ('negotiate', 'too_much', ['You tell me.', 'What is the smallest amount I can pay?']),
        ('negotiate', 'question', ['You tell me what the deadline means.']),
        ('negotiate', 'too_much', ['Can you offer a smaller payment?']),
        ('negotiate', 'accepts', ['Yes, I can pay on Friday the sixteenth.']),
        ('negotiate', 'accepts', ['Friday the sixteenth, yes, that works.']),
        ('negotiate', 'proposes', ['Yes, actually no, I need the twentieth instead.']),
        ('negotiate', 'too_much', ['I agree, sorry, no, that is too much; suggest less.']),
        ('negotiate', 'question', ['How much did you just say?']),
        ('negotiate', 'other', ['You tell me.']),
        ('opening', 'unclear', ['Who is calling?']),
        ('opening', 'unclear', ['Go on, I am listening.']),
        ('readback', 'changes', ['Yes, correct, actually change it to three hundred and fifty.']),
        ('readback', 'question', ['Do you mean this Friday or next Friday?']),
        ('third_party', 'gives_time', ['Tomorrow morning.', 'Around eleven.']),
        ('third_party', 'gives_time', ['Tomorrow.', 'In the morning.', 'Around eleven.']),
        ('third_party', 'gives_time', ['Tomorrow around...', '...eleven in the morning.']),
        ('third_party', 'gives_time', ['Morning.']),
        ('third_party', 'gives_time', ['Tomorrow at three, sorry, around eleven in the morning.']),
    ]
    for i, (group, expected, turns) in enumerate(extras):
        item = dict(id=f'boundary-{i+1:02d}', group=group, variable=GROUPS[group][0], expected=expected,
                    style='boundary', turns=turns, ambiguity='underspecified' if turns == ['You tell me.'] else None)
        if group == 'third_party':
            item['expected_time'] = '' if turns == ['Morning.'] else '11:00'
            item['no_time_before_final'] = len(turns) > 1
        cases.insert(i, item)
    return cases


def snapshot(out):
    spec = importlib.util.spec_from_file_location('compiler_under_test', ROOT / 'compile.py')
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    ir = policy.PolicyIR.load(str(ROOT / 'tests/fixtures/brief_a.policy.json'))
    full = compiler.compile_workflow(ir, compiler.parse_openapi(str(ROOT / 'tools/openapi.json')))
    nodes = full['nodes']
    identity = next(k for k, v in nodes.items() if k.startswith('ask_') and any(e['name']=='id_digits' for e in v.get('extraction_schema', [])))
    selected = {g: copy.deepcopy(nodes[identity if g == 'identity' else g]) for g in GROUPS}
    save_json(out / 'schemas.json', selected)
    source = (ROOT / 'compile.py').read_bytes()
    (out / 'compile.snapshot.txt').write_bytes(source)
    save_json(out / 'metadata.json', dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        compile_sha256=hashlib.sha256(source).hexdigest(), model=freya.AGENT_LLM, slot='runtime-check',
        styles=STYLES, method='Serial chat-only; unmodified extraction schemas; isolated call per case; inert routes; no bank actions.'))
    save_json(out / 'cases.json', corpus())


def workflow(group, node):
    node = copy.deepcopy(node)
    node['name'] = 'probe'
    node['on_enter'] = {'type': 'tts', 'text': CONTEXT[group]}
    node['on_enter_first_entry_only'] = True
    node['task_message'] = ('You are collecting the answer to: ' + CONTEXT[group] +
        ' If the caller trails off, ask them to finish. If they ask a question, answer briefly. '
        'Do not invent an amount, date, time or consent. Do not say any action has been recorded. '
        'Keep replies short. For a callback, ask for the missing day or exact clock time. Otherwise ask them to clarify or continue.')
    # Keep the original enum routing condition, but make its destination inert.
    transitions = []
    for t in node['transitions']:
        if t.get('condition', {}).get('operator') != 'always':
            t['target_node'] = 'routed'
            transitions.append(t)
    node['transitions'] = transitions + [{'target_node': 'probe', 'condition': {'operator':'always'}, 'description':'Continue collecting'}]
    node['max_node_turns'] = 12
    node['max_turn_transition'] = 'probe'
    # Identical collection in the inert node lets pieces continue without executing
    # production code that would clear fragments or perform bank actions.
    routed = copy.deepcopy(node)
    routed['name'] = 'routed'
    routed['on_enter'] = {'type': 'llm'}
    routed['on_enter_first_entry_only'] = False
    return dict(initial_node='probe', system_prompt='You are a bank telephone assistant in an isolated extraction test. Speak English. No tools or bank actions are available.', nodes=dict(probe=node, routed=routed))


def run_case(ids, case, out):
    folder = out / 'calls'
    folder.mkdir(exist_ok=True)
    call_id = None
    records = []
    started = time.monotonic()
    variables = dict(now='2026-10-14T11:00', title='Mr', first_name='Alex', last_name='Morgan',
                     neg_instruction=CONTEXT[case['group']], readback_text=CONTEXT['readback'],
                     product_list='1: credit card', id_say=CONTEXT['identity'])
    try:
        for index, speech in enumerate(['Hello.'] + case['turns']):
            body = dict(workflowId=ids['workflow_id'], message=speech)
            body.update(dict(callId=call_id) if call_id else dict(customerVariables=variables))
            response = freya.api('POST', '/api/v2/chat/message', body)
            call_id = response['callId']
            call = freya.get_call(call_id)
            save_json(folder / (case['id'] + '.call.json'), call)
            values, events = variables_from(call)
            records.append(dict(speech=speech, response=response.get('response'), values=values,
                                routed=any(e.get('matched') and e.get('target') == 'routed' for e in events)))
            save_json(folder / (case['id'] + '.turns.json'), records)
        final = records[-1]['values']
        actual = final.get(case['variable'])
        result = dict(**case, call_id=call_id, actual=actual, passed=actual == case['expected'],
                      duration_s=round(time.monotonic()-started, 2), status='completed', turns_observed=records[1:])
        if 'expected_time' in case:
            result['actual_time'] = final.get('cb_time') or ''
            result['time_passed'] = result['actual_time'] == case['expected_time']
            if case.get('no_time_before_final'):
                result['time_passed'] &= all(not r['values'].get('cb_time') for r in records[1:-1])
        return result
    except Exception as exc:
        return dict(**case, status='infrastructure_error', error=str(exc), call_id=call_id,
                    duration_s=round(time.monotonic()-started,2), turns_observed=records[1:])
    finally:
        if call_id:
            try:
                freya.api('POST', '/api/v2/chat/end', dict(callId=call_id))
            except Exception as exc:
                save_json(folder / (case['id'] + '.end-error.json'), {'error': str(exc)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resume', type=Path)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--group', choices=list(GROUPS))
    ap.add_argument('--style', choices=list(STYLES)+['boundary'])
    ap.add_argument('--boundary-sample', action='store_true', help='Small breadth sample across intent values and styles')
    ap.add_argument('--skip-errors', action='store_true', help='Continue breadth coverage without retrying previously failed requests')
    ap.add_argument('--prepare-only', action='store_true')
    args = ap.parse_args()
    out = args.resume or ROOT / 'results/extraction' / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out.mkdir(parents=True, exist_ok=True)
    if not (out / 'schemas.json').exists():
        snapshot(out)
    print('Artifacts:', out, flush=True)
    if args.prepare_only:
        return
    cases = json.loads((out / 'cases.json').read_text())
    schemas = json.loads((out / 'schemas.json').read_text())
    results_path = out / 'results.json'
    results = json.loads(results_path.read_text()) if results_path.exists() else []
    done = {r['id'] for r in results if r['status'] == 'completed' or args.skip_errors}
    pending = [c for c in cases if c['id'] not in done and (not args.group or c['group']==args.group) and (not args.style or c['style']==args.style)]
    if args.boundary_sample:
        chosen = []
        for group in GROUPS:
            for style in STYLES:
                subset = [c for c in pending if c['group']==group and c['style']==style]
                if subset:
                    chosen.append(subset[0])
        pending = chosen
    if args.limit:
        pending = pending[:args.limit]
    pending.sort(key=lambda c: list(GROUPS).index(c['group']))
    current, ids, errors = None, None, 0
    for case in pending:
        if current != case['group']:
            current = case['group']
            pub = out / ('published-' + current)
            pub.mkdir(exist_ok=True)
            ids = publish(workflow(current, schemas[current]), pub)
        result = run_case(ids, case, out)
        results.append(result)
        save_json(results_path, results)
        print(json.dumps({k:result[k] for k in ('id','status','expected','actual','passed','duration_s','error') if k in result}), flush=True)
        errors = errors + 1 if result['status'] != 'completed' else 0
        if errors >= 3:
            print('Stopping after three consecutive infrastructure errors; resume is supported.', flush=True)
            break
    print('Finished', len(results), 'attempts;', sum(r['status']=='completed' for r in results), 'completed', flush=True)


if __name__ == '__main__':
    main()
