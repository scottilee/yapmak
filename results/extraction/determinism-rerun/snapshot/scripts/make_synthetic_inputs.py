"""Generate offline cases using unchanged public identities/products and explicit harness limits."""
import copy
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/fixtures/synthetic'
OUT.mkdir(parents=True, exist_ok=True)
cases={c['id']:c for c in json.loads((ROOT/'public-test-set.json').read_text())}
manifest=[]


def write(name, base, script, expected, checks, support='official_cases', requirements=None, now=None):
    case=copy.deepcopy(cases[base])
    case.update(title=name.replace('_',' '), script=script, expected=expected, checks=checks)
    if now:
        case['variables']['now']=now
    (OUT/(name+'.json')).write_text(json.dumps([case],indent=2))
    manifest.append(dict(name=name, file=name+'.json', case_id=base, support=support, requirements=requirements or [],
                         identity_and_products_unchanged=True))


def expected(promises=(), notes=(), outcome='promise', reason=None, transfers=()):
    return dict(outcome=outcome, reason=reason, promises=list(promises), notes=list(notes), callbacks=[], transfers=list(transfers))


write('readback_amount_correction','PUB-01',
      'Confirm your name and give the correct security answers when asked. Agree to pay 420 dollars today. At the first read-back say: "Yes, but change the amount to three hundred and fifty dollars." Do not confirm the old amount. Confirm only after the assistant reads back 350 dollars for today.',
      expected([dict(product_id='p1',amount=350,date='2026-10-14')]),
      ['No promise written before confirmation of the revised 350-dollar read-back','Exactly one promise for 350, never for 420','Text-message sentence follows a successful write'])
write('below_floor_then_accept','PUB-06',
      'Confirm your name and give correct security answers. Say the full amount is too much and propose 100 dollars this Friday. When told the floor is 637.50, accept that floor for Friday. Confirm its read-back.',
      expected([dict(product_id='p1',amount=637.5,date='2026-10-16')]),
      ['100 dollars is rejected without a promise write','Floor offered with explanation that the remainder stays overdue','Record 637.50 on 16 October only after confirmation'])
write('next_friday_from_friday','PUB-01',
      'Confirm your name and give correct security answers. You cannot pay today, Friday 16 October. Offer the full 420 dollars next Friday. You mean Friday 23 October. Confirm only that date at read-back.',
      expected([dict(product_id='p1',amount=420,date='2026-10-23')]),
      ['Next Friday resolves to 23 October from simulated Friday 16 October','No use of the real clock','One confirmed promise'],
      support='requires_now_adapter', requirements=['Official run_cases.py uses server session variables and ignores the JSON now override. Use scripts/run_synthetic_cases.py.'], now='2026-10-16T11:00')
write('dispute_second_of_three','PUB-11',
      'Confirm your name and give correct security answers. After all products are stated, say you will pay the credit card 220 dollars this Friday, but the personal loan is not yours. Flatly refuse the car loan after its permitted persuasion attempt. Confirm only the credit-card promise at the batch read-back.',
      expected([dict(product_id='p1',amount=220,date='2026-10-16')], [dict(product_id='p2',reason='dispute'),dict(product_id='p3',reason='refused')]),
      ['Dispute applies only to product p2 and does not abandon other products','Only p1 gets a promise','One dispute note for p2, one refused note for p3','Close as promise'])
write('transfer_after_recorded_promise','PUB-11',
      'Confirm your name and give correct security answers. Offer 220 dollars on the credit card this Friday, dispute the personal loan, and flatly refuse the car loan. Confirm only the credit-card read-back. As soon as the assistant says the credit-card promise was successfully recorded, immediately request lower instalments and a new payment plan for the personal loan. Do not request restructuring before the promise is recorded.',
      expected([dict(product_id='p1',amount=220,date='2026-10-16')],outcome='transferred',reason='restructuring',transfers=[dict(queue='restructuring')]),
      ['Recorded p1 promise survives transfer','Transfer is to restructuring','No notes at all, including before transfer','Final outcome is transferred/restructuring'],
      support='script_requires_interruption_opportunity',requirements=['This script can run with --cases, but only reaches its trigger if the workflow allows a customer turn after acknowledging persistence and before writing pending notes/closing. Use controlled chat for deterministic coverage.'])
case=copy.deepcopy(cases['PUB-11'])
case['faults']=[dict(tool='create_promise',product_id='p2',fail_first_n=2)]
case['script']='Verify correctly. Agree to pay all three products this Friday and confirm the batch once. If told a product could not be recorded, acknowledge it. Do not invent another offer.'
case['title']='Double failure for product 2; preserve products 1 and 3'
case['expected']=expected([dict(product_id='p1',amount=220,date='2026-10-16'),dict(product_id='p3',amount=75,date='2026-10-16')],[dict(product_id='p2',reason='service_error')])
case['checks']=['Two failed write attempts for p2, then one service_error note','Promises p1 and p3 remain','Never claim p2 was recorded','Final outcome promise']
(OUT/'double_write_failure.json').write_text(json.dumps([case],indent=2))
manifest.append(dict(name='double_write_failure',file='double_write_failure.json',case_id='PUB-11',support='offline_fault_fixture_only',identity_and_products_unchanged=True,
                     requirements=['Official runner does not send faults or products to /v1/practice/sessions. No documented per-product double-failure injection is provided. Do not label this runnable via --cases until such support exists.']))
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
# Mutated briefs: systematic, offline fixtures with explicit expected differences.
BRIEFS=ROOT/'tests/fixtures/mutated_briefs'; BRIEFS.mkdir(exist_ok=True)
a=(ROOT/'briefs/brief-a.md').read_text()
variants=[('calendar_and_limits', a.replace('2026-10-26','2026-10-27').replace('12th business day','10th business day').replace('7th business day','5th business day'),
           dict(early_n=10,late_n=5,holiday_replaced=['2026-10-26','2026-10-27'])),
          ('identity_order',a.replace('first the date of birth, then the last four digits of the phone number on file','first the last four digits of the phone number on file, then the date of birth'),dict(identity_order=['phone_last4','date_of_birth'])),
          ('callback_window',a.replace('10:00 to 19:00','09:00 to 17:00'),dict(callback_start='09:00',callback_end='17:00'))]
meta=[]
for name,text,assertions in variants:
    (BRIEFS/(name+'.md')).write_text(text)
    meta.append(dict(file=name+'.md', expected_changes=assertions, support='offline_policy_extraction'))
(BRIEFS/'effective_memo.md').write_text('Effective 15 October 2026. This memo replaces only the callback-hours clause in rule 6: callbacks are from 09:00 to 17:00 inclusive. Other rules remain in force.\n')
meta.append(dict(file='effective_memo.md',combine_with='briefs/brief-a.md',expected_changes=dict(callback_start='09:00',callback_end='17:00',effective_date='2026-10-15'),support='offline_precedence_and_scope'))
(BRIEFS/'manifest.json').write_text(json.dumps(meta,indent=2))
print('Created',len(manifest),'synthetic scripts and',len(meta),'brief mutation inputs.')
