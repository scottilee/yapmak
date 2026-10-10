"""Author two independent synthetic policy fixtures and pre-extraction value oracles."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/fixtures/synthetic'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def make_api(stem, identity, types, floor_names, prefix):
    api = json.loads((OUT / 'memo-openapi.json').read_text())
    api['info']['title'] = prefix + ' synthetic bank API'
    api['info']['version'] = 'synthetic-1'
    # Non-live host: these schemas are publication fixtures, not public mock data.
    api['servers'] = [{'url': 'https://' + stem + '.example.invalid/v1'}]
    def request(name):
        return api['paths']['/' + name]['post']['requestBody']['content']['application/json']['schema']
    def response(name):
        return api['paths']['/' + name]['post']['responses']['200']['content']['application/json']['schema']
    api['paths']['/verify_identity']['post']['summary'] = 'Check one security answer. The supplied brief defines question order and the total wrong-answer allowance; checks_left is authoritative.'
    api['paths']['/get_account']['post']['summary'] = 'Return overdue products only after every identity question required by the supplied brief has passed.'
    api['paths']['/add_note']['post']['summary'] = 'Record the permitted reason for a product without a promise, only when the supplied brief authorizes a note.'
    request('verify_identity')['properties']['field']['enum'] = identity
    request('verify_identity')['properties']['answer']['description'] = 'postcode: letters and digits without spaces; birth_year/founded_year: four-digit year; company_number: exactly eight digits. Verify in the order in the supplied brief.'
    for name in ('verify_identity','get_account','create_promise','add_note','schedule_callback','transfer_to_agent','close_call'):
        responses = api['paths']['/' + name]['post']['responses']
        responses['200']['description'] = '`success` is false when the bank action was not carried out.'
        if '500' in responses:
            responses['500']['description'] = 'The service failed and nothing was recorded. Retry only if the effective brief permits it.'
        props = response(name)['properties']
        props['success'] = props.pop('ok')
        props['success']['description'] = 'True only when the bank operation succeeded; HTTP status alone does not authorize a success claim.'
    vp = response('verify_identity')['properties']
    vp['answer_verified'] = vp.pop('verified')
    vp['checks_left'] = vp.pop('attempts_remaining')
    vp.pop('hint', None)
    account = response('get_account')['properties']
    account['accounts'] = account.pop('facilities')
    product = account['accounts']['items']['properties']
    product['account_id'] = product.pop('product_id')
    product['kind'] = product.pop('type')
    product['kind']['enum'] = types
    product['overdue_balance'] = product.pop('arrears')
    product['late_days'] = product.pop('days_in_arrears')
    product.pop('minimum_due'); product.pop('scheduled_repayment')
    for typ, floor in zip(types, floor_names):
        product[floor] = {'type':'number', 'description': 'Minimum permitted promise amount for ' + typ + ' only.'}
    outcomes = {k: prefix + '_' + k for k in ('arranged','settled','transferred','no_deal','unverified','unreached')}
    reasons = {k: prefix + '_' + k for k in ('refused','distress','disputed','settled','service_error','restructure','person','care','failed','declined','callback','no_callback','wrong_number','deceased','unclear')}
    queues = {k: prefix + '_' + k for k in ('restructure','desk','care')}
    request('close_call')['properties']['outcome']['enum'] = list(outcomes.values())
    request('close_call')['properties']['reason'] = {'type':'string','enum':list(reasons.values()),'description':'Omit for arranged and settled outcomes. Other outcome/reason combinations are constrained by the brief.'}
    request('add_note')['properties']['reason']['enum'] = [reasons[k] for k in ('refused','distress','disputed','settled','service_error')]
    request('transfer_to_agent')['properties']['queue']['enum'] = list(queues.values())
    write_json(OUT / (stem + '-openapi.json'), api)
    return outcomes, reasons, queues


def build(stem, bank, identity, types, floor_names, prefix, messy=False):
    o, r, q = make_api(stem, identity, types, floor_names, prefix)
    questions = {
        'postcode': ('What is the registered business postcode?', 'text', 0),
        'birth_year': ('In what year were you born?', 'year', 0),
        'company_number': ('What is the eight-digit company registration number?', 'digits', 8),
        'founded_year': ('In what year was the company founded?', 'year', 0),
    }
    opening = f'Good day, this is {bank}\'s automated assistant. We record this call.'
    holiday = ['2026-10-30','2026-11-02','2026-12-25','2027-01-01'] if not messy else ['2026-10-19','2026-11-02','2026-12-24','2027-01-01']
    names = {types[0]:'working capital line', types[1]:'asset finance loan', types[2]:'merchant advance'}
    table = {o['arranged']:[],o['settled']:[],o['transferred']:[r[k] for k in ('restructure','person','care')],o['no_deal']:[r[k] for k in ('refused','distress','disputed','service_error')],o['unverified']:[r[k] for k in ('failed','declined')],o['unreached']:[r[k] for k in ('callback','no_callback','wrong_number','deceased','unclear')]}
    identity_text = '\n'.join(f'   {i+1}. `{field}`: "{questions[field][0]}" Answer format: {questions[field][1]}; '+('exactly eight digits, preserving leading zeros.' if field=='company_number' else 'four-digit year.' if questions[field][1]=='year' else 'letters and digits only; strip spaces.') for i,field in enumerate(identity))
    deadlines = ('Days late 1–45 inclusive: the latest promise date is the last business day of the current calendar month. '
        'Use end_of_month with basis=business and adjustment=preceding. This means the greatest business date on or before the calendar month end, never the next month. '
        'There is one persuasion attempt: full overdue balance on the deadline, substituting the floor only if full has already been refused.' if not messy else
        'Days late 1–15 inclusive: the latest promise date is the 9th business day after today; one persuasion attempt. '
        'Days late 16–60 inclusive: the latest promise date is the 6th business day after today; two persuasion attempts. '
        'In both bands attempt 1 offers the full overdue balance on the last business day of this week (next week if today is that day), substituting the floor if full was already refused. '
        'Attempt 2, only in the 16–60 band, offers the floor on the deadline.')
    body = f'''1. OPENING AND PRIVACY. Start exactly: "{opening}" Then ask exactly: "Am I speaking with {{{{title}}}} {{{{last_name}}}}?" Address the customer as title and last name. A clear yes, speaking, or their own name confirms the holder. Hello or a question does not. Ask at most twice in total; if still unclear close `{o['unreached']}` / `{r['unclear']}`. Before ALL verification answers pass, never say these words or disclose their associated information: arrears, overdue, facility, payment. Call variables are customer_id, first_name, last_name, title, now.

2. THIRD PARTIES. Disclose nothing about purpose or accounts. Ask when the holder can be reached. Callbacks are on {'today or the next business day' if messy else 'the next business day only'}, between {'09:15 and 17:45' if messy else '08:30 and 16:15'} inclusive, strictly after now. A missing hour must be clarified, never guessed. For an invalid slot ask once for another; a second failure or refusal closes `{o['unreached']}` / `{r['no_callback']}`. A successfully scheduled callback closes `{o['unreached']}` / `{r['callback']}`. Wrong number: `{o['unreached']}` / `{r['wrong_number']}`. Deceased holder: say exactly "Please accept our condolences." and close `{o['unreached']}` / `{r['deceased']}`.

3. SECURITY. Ask these {len(identity)} questions, one at a time, in precisely this order, calling verify_identity after each completed answer:
{identity_text}
   Maximum wrong answers across the entire check: {'2' if messy else '4'}. Use the API's checks_left, not a separate per-question allowance. On exhaustion say exactly "Please contact our business desk." and close `{o['unverified']}` / `{r['failed']}`. Explain account protection once after a refusal; a second refusal closes `{o['unverified']}` / `{r['declined']}`. A question about why security is needed does NOT count as a refusal; answer and ask again. The API provides no recoverable-format hint, so no hint rule applies. Do not call get_account until all questions pass.

4. ACCOUNT AND CALENDAR. After verification call get_account. Up to {'3' if messy else '2'} products may be returned in accounts. account_id is the product identifier to pass as product_id in write requests; kind is the product type, overdue_balance the full amount, and late_days the lateness. Name types as follows: {json.dumps(names)}. State all products and their amounts/days late before asking anything. All dates use call variable now, never the machine clock. Business days are Monday through Friday except {', '.join(holiday)}. "Next Friday" means Friday of the following calendar week, including when today is Friday; "this Friday" means the current week's Friday. For a missing month/year choose the next occurrence of the named day/date on or after today. No other holidays apply.

5. DEADLINES AND ATTEMPTS. {deadlines} Today is not counted when counting business days after today. First ask exactly "Can you settle all these products today?" once for all products; for a single product use "Can you settle this today?". A flat refusal consumes one persuasion attempt. Process products in get_account order with separate attempt counters. At exhaustion mark the product `{r['refused']}`. A common date after a product's deadline is clamped to that product's own deadline and explained in the read-back.

6. AMOUNTS AND DATES. Ask for full overdue balance first. Floors by kind are {json.dumps(dict(zip(types,floor_names)))}; the values come from those get_account fields. On full being too much, offer the floor once per product and say exactly "The remainder stays overdue." Never ask how much they can pay. Accept an amount between floor and full inclusive; never accept less than floor or more than full. A promise date may be today, must be a business day and not exceed the deadline. Roll weekends/holidays forward only if the resulting business date is within deadline; otherwise offer the deadline. Ask once to clarify a vague period, then propose the deadline. Never offer a discount, waiver or a new instalment plan.

7. READ-BACK AND WRITES. Read back product, amount and date for all proposed payments in one batch. Ask exactly "May I record these promises?" A clear yes to the unchanged batch is required; any correction invalidates consent and requires a new read-back. One create_promise per product, at most one successful promise per product. If a write fails, {'retry it once' if messy else 'retry it once'}; a second failure marks only that product `{r['service_error']}`, says it failed, and continues the other products. Never claim a failed write was recorded. After a successful promise say exactly "We will email confirmation to your registered address." If asked to change an already recorded promise, say exactly "Please contact our business desk to change a recorded promise."

8. SPECIAL CASES. Handle these before persuasion. Already paid: say exactly "Payments can take two business days to appear.", take no new promise for that product, mark `{r['settled']}` and continue other products. Dispute (not their debt, never held it, or it was closed/paid off earlier): do not argue or take a promise for it; mark `{r['disputed']}` and continue. Hardship means illness, bereavement or job loss: one short sentence of sympathy, no persuasion and no promise for the affected product. Offer queue `{q['care']}`; if accepted transfer and close `{o['transferred']}` / `{r['care']}`, otherwise mark `{r['distress']}` and continue other products. A request to restructure or reduce instalments transfers immediately to `{q['restructure']}` and closes `{o['transferred']}` / `{r['restructure']}`. A request for a human: ask once if this assistant can help; if they insist, transfer to `{q['desk']}` and close `{o['transferred']}` / `{r['person']}`. A refusal to talk: ask once if you may continue; a second refusal ends the call and marks all remaining products `{r['refused']}`. If asked whether this is a robot say exactly "I am {bank}'s automated assistant." If asked about a scam say exactly "You can call the number on your bank statement to verify us." and continue. If unable to answer another question, say exactly "Our business desk can answer that question."

9. NOTES AND FINAL OUTCOME. On a non-transfer call, after processing all products, add exactly one note per unpromised product, using only {', '.join(r[k] for k in ('refused','distress','disputed','settled','service_error'))}. Never add notes on a transferred call, including before transfer; defer notes until the non-transfer outcome is known. A transfer cancels unrecorded proposals but keeps already recorded promises. Outcome precedence: transfer overrides any promise; otherwise at least one recorded promise gives `{o['arranged']}`; otherwise all products settled gives `{o['settled']}`; otherwise `{o['no_deal']}` with the first non-settled product's note reason in get_account order. Exactly one close_call is the last bank action. Thank the customer and say goodbye before calling it. Debt introduction after verification is exactly "I am calling about the overdue business products."

10. OUTCOME CODE TABLE. These are the only allowed combinations; omit reason entirely for rows with none:
''' + '\n'.join(f'{outcome}: '+(' | '.join(reasons) if reasons else '(no reason)') for outcome,reasons in table.items())
    if not messy:
        text = f'# {bank}: automated collections specification\n\nDocument ID CLEAN-EOM-1. Effective 14 October 2026. This is a complete synthetic specification; no other policy or amendment applies. Use only this document and clean-eom-openapi.json.\n\n' + body + '\n'
    else:
        text = f'''From: Digital Delivery <delivery@harbour-example.invalid>
Date: 10 October 2026, 09:40 UTC
Subject: Fwd: the launch pack — use signed Risk R7, NOT my old email

Team, this is the complete synthetic launch pack. Below are the signed memo, the older operations extract it amends, and a forwarded email. Please read all of it. The later position of a quotation in this email does not give it authority. All live calls for this fixture use the post-memo policy.

--- Attachment pasted first: SIGNED RISK MEMO R7 ---
Issued 9 October 2026, 16:00 UTC; effective 10 October 2026, 00:00 UTC.
Authority: Risk Director. Explicit amendment of Harbour Commercial operational policy P3 below. Applicable to this entire digital outbound portfolio; no other product scope or future effective date.

R7-A. Reverse P3 rule 7: NEVER retry a failed create_promise. Exactly one request per product. On the first failure mark that product `{r['service_error']}`, tell the customer no promise was recorded for it, and continue other products. The earlier instruction to retry once is withdrawn.
R7-B. Reverse P3 rule 8's human-request barrier: transfer immediately to `{q['desk']}` on the FIRST explicit request for a human. Do not ask whether the assistant can help first. Outcome/reason stay `{o['transferred']}` / `{r['person']}`.
R7-C. Change ONLY the 16–60 days-late band's deadline from the 6th to the 4th business day after today. The 1–15 band's 9-business-day deadline and both bands' attempt counts are unchanged.
R7-D. Replace P3's callback day eligibility: NEXT BUSINESS DAY ONLY, never today. Hours remain 09:15–17:45 inclusive; keep the one alternative-slot attempt.
R7-E. Everything else in P3, including identity order, holidays, floors, code list and no notes on transfer, remains in force. This memo outranks earlier operational emails even if they appear below it in a forwarded thread.

--- Attachment pasted second: OPERATIONS POLICY P3 ---
Effective 1 October 2026; signed by Operations. This is the baseline amended by R7.
{body}

--- Forwarded message (historical, NOT a new instruction) ---
From: Operations rollout <rollout@harbour-example.invalid>
Date: 2 October 2026, 11:20 UTC
Subject: Re: retry behaviour and customer transfers

Quoting our P3 launch checklist: "Retry every failed promise once. Ask whether the assistant can help before transferring to a human. Today is fine for a callback. The late band's deadline is six business days."

--- Delivery annotation, 10 October ---
That quotation is retained for the audit trail only. It is superseded by signed R7-A through R7-D. Do not reinstate it. The JSON tool schema is reversal-thread-openapi.json; renamed code values in it match P3's table above.
'''
    (OUT / (stem+'-brief.md')).write_text(text)
    checks = {}
    def expect(path,value,source):
        checks[path] = {'expected':value,'source':source}
    expect('bank_name',bank,'document title')
    expect('identity.requirements.$fields',identity,'rule 3 order')
    for i,field in enumerate(identity):
        expect(f'identity.requirements.{i}.answer_format',questions[field][1],'rule 3')
        expect(f'identity.requirements.{i}.digits',questions[field][2],'rule 3')
        expect(f'identity.requirements.{i}.hint_field','','rule 3: no hint')
    for path,value in {
        'identity.wrong_answer_limit':2 if messy else 4,'identity.wrong_count_source':'api','identity.remaining_slot':'checks_left',
        'identity.holder_confirmation_asks':2,'identity.decline_explain_once':True,'identity.asking_purpose_counts_as_decline':False,
        'identity.failed_outcome':[o['unverified'],r['failed']],'identity.declined_outcome':[o['unverified'],r['declined']],
        'identity.unclear_holder_outcome':[o['unreached'],r['unclear']], 'identity.failed_instruction':'Please contact our business desk.',
        'third_party.callback.enabled':True,'third_party.callback.days':'next_business_day','third_party.callback.start':'09:15' if messy else '08:30',
        'third_party.callback.end':'17:45' if messy else '16:15','third_party.callback.must_be_after_now':True,'third_party.callback.retry_once':True,
        'third_party.callback.scheduled_outcome':[o['unreached'],r['callback']],'third_party.callback.no_callback_outcome':[o['unreached'],r['no_callback']],
        'third_party.wrong_number_outcome':[o['unreached'],r['wrong_number']],'third_party.deceased_outcome':[o['unreached'],r['deceased']],
        'third_party.deceased_sentence':'Please accept our condolences.',
        'calendar.holidays':holiday,'calendar.business_days':[0,1,2,3,4],'calendar.next_weekday_means_following_week':True,'calendar.missing_date_parts':'next_occurrence',
        'amounts.floors':dict(zip(types,floor_names)),'amounts.full_first':True,'amounts.never_ask_how_much':True,'amounts.floor_offered_once':True,
        'amounts.floor_wording':'The remainder stays overdue.','amounts.accept_between_floor_and_full':True,
        'dates.promise_today_allowed':True,'dates.weekend_or_holiday_roll_forward':True,'dates.vague_ask_once_then_deadline':True,'dates.after_deadline_offer_deadline':True,
        'promise_write.retry_on_failure':0 if messy else 1,'promise_write.one_promise_per_product':True,'promise_write.confirm_phrase':'May I record these promises?',
        'notes.enabled':True,'notes.reasons':[r[k] for k in ('refused','distress','disputed','settled','service_error')],'notes.note_each_unpromised_product':True,'notes.none_on_transfer':True,
        'multi_product.max_products':3 if messy else 2,'multi_product.state_all_before_asking':True,'multi_product.ask_all_today_once':True,
        'multi_product.per_product_attempts':True,'multi_product.common_date_clamped_per_product':True,'multi_product.one_confirmation_for_batch':True,'multi_product.recorded_promises_survive_transfer':True,
        'outcomes.$table':table,'outcomes.promise_outcome':o['arranged'],'outcomes.paid_outcome':o['settled'],'outcomes.transfer_outcome':o['transferred'],
        'outcomes.no_promise_outcome':o['no_deal'],'outcomes.transfer_overrides_promise':True,'outcomes.all_paid_closes_as_paid':True,
        'outcomes.no_promise_reason_from_first_non_paid_note':True,'outcomes.service_error_reason':r['service_error'],'outcomes.refused_reason':r['refused'],'outcomes.goodbye_before_close':True,
        'phrases.opening':opening,'phrases.holder_question':'Am I speaking with {{title}} {{last_name}}?',
        'phrases.debt_intro':'I am calling about the overdue business products.','phrases.today_question':'Can you settle this today?',
        'phrases.all_today_question':'Can you settle all these products today?','phrases.robot_reply':f'I am {bank}\'s automated assistant.',
        'phrases.scam_reply':'You can call the number on your bank statement to verify us.',
        'phrases.prohibited_before_verification':['arrears','overdue','facility','payment'],
        'phrases.after_promise_sentence':'We will email confirmation to your registered address.',
        'phrases.already_paid_sentence':'Payments can take two business days to appear.',
        'phrases.cannot_answer_sentence':'Our business desk can answer that question.',
        'phrases.recorded_promise_change_reply':'Please contact our business desk to change a recorded promise.',
        'phrases.product_naming':names,
    }.items():
        expect(path,value,'P3 + R7 where amended' if messy else 'clean numbered specification')
    attempt = {'amount':'full','date':'last_business_day_this_week_or_next' if messy else 'deadline','floor_if_full_refused':True}
    bands = [{'days_late_min':1,'days_late_max':15,'deadline':{'kind':'nth_business_day','n':9},'attempts':[attempt]},
             {'days_late_min':16,'days_late_max':60,'deadline':{'kind':'nth_business_day','n':4},'attempts':[attempt,{'amount':'floor','date':'deadline','floor_if_full_refused':True}]}] if messy else [
                 {'days_late_min':1,'days_late_max':45,'deadline':{'kind':'end_of_month','basis':'business','adjustment':'preceding'},'attempts':[attempt]}]
    expect('bands.$rules',bands,'R7-C overrides only late band' if messy else 'rule 5')
    sc = {
        'already_paid':{'action':{'type':'note','reason':r['settled']},'takes_promise':False,'ends_call':False},
        'dispute':{'action':{'type':'note','reason':r['disputed']},'takes_promise':False,'ends_call':False},
        'hardship':{'action':{'type':'note','reason':r['distress']},'takes_promise':False,'ends_call':False,'offer_transfer_queue':q['care'],'offer_outcome':[o['transferred'],r['care']]},
        'restructuring':{'action':{'type':'transfer','queue':q['restructure'],'outcome':o['transferred'],'reason':r['restructure']},'takes_promise':False,'ends_call':True},
        'human':{'action':{'type':'transfer','queue':q['desk'],'outcome':o['transferred'],'reason':r['person']},'ask_once_first':not messy,'takes_promise':False,'ends_call':True},
        'scam':{'action':{'type':'continue'},'ends_call':False,'say':'You can call the number on your bank statement to verify us.'},
        'refuse_to_talk':{'action':{'type':'close','outcome':o['no_deal'],'reason':r['refused']},'ask_once_first':True,'takes_promise':False,'ends_call':True},
    }
    for name,values in sc.items():
        for field,value in values.items():
            expect('special_cases.'+name+'.'+field,value,'R7-B' if messy and name=='human' else 'rule 8')
        expect('special_cases.'+name+'.before_persuasion',True,'rule 8: all special cases before persuasion')
    write_json(OUT/(stem+'-expected.json'),{'fixture':stem,'brief':stem+'-brief.md','openapi':stem+'-openapi.json','checks':checks,
        'comparison_notes':['Expected values authored before extraction; source spans, free prose triggers and arbitrary band names require manual semantic review.',
                            'Outcome tables and note/holiday sets are compared without order; identity and attempt order are significant.',
                            'Different but equivalent special-case action representations are flagged for manual review, not automatically called errors.',
                            'No public mock simulations: identities/products/schema differ; .example.invalid tool endpoints prevent accidental bank writes.']})


if __name__=='__main__':
    build('clean-eom','Larkspur Business Bank',['postcode','birth_year','company_number','founded_year'],['working_line','asset_credit','merchant_credit'],['minimum_remittance','scheduled_minimum','merchant_floor'],'lark')
    build('reversal-thread','Harbour Commercial',['company_number','postcode','founded_year'],['revolver','plant_loan','sales_advance'],['revolver_floor','plant_due','advance_floor'],'harbour',True)
