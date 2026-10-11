"""Direct offline function probes only; no workflow driver or external calls."""
import copy, datetime, hashlib, json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import bankcal as bc
import compile as C
import policy as P
base = json.loads((ROOT/'tests/fixtures/brief_a.policy.json').read_text())
def env(policy=None):
    ns = dict(vars={'now':'2026-10-14T11:00'}, POLICY=copy.deepcopy(policy or base), SLOTS={}, EMPTY=C.EMPTY_VALUES, json=json, datetime=datetime)
    ns.update({k:v for k,v in vars(bc).items() if not k.startswith('__')})
    exec((ROOT/'workflow_runtime.py').read_text(), ns)
    s=ns['_fresh_state']()
    p=dict(product_id='p1', type='credit_card', name='credit card', full=420., floor=100., deadline='2026-10-23', no_window=False, attempts=copy.deepcopy(base['bands'][0]['attempts']), attempts_used=0, full_refused=False, floor_offered=False, proposed=True, proposed_amount=420., proposed_date='2026-10-14', clamped=False, recorded=False, write_failures=0, disposition='')
    s['products']=[p]; ns['_save'](s)
    return ns,s,p
out={}
n,s,p=env(); n['vars'].update(rb_intent='confirms', aside='robot'); n['_run']('readback_route')
out['confirmation_aside']={k:n['vars'].get(k) for k in ('next','neg_instruction','goodbye_text')}
s=n['_S']();s['products'][0]['recorded']=True;n['_save'](s);n['st_finalize']()
out['confirmation_aside']['final_goodbye']=n['vars']['goodbye_text']
d=copy.deepcopy(base); d['dates']['past_deadline']='no_promise'
for band in d['bands']: band['deadline']=dict(kind='day_of_month', day=1, month_offset=0, adjustment='preceding')
n,s,p=env(d); n['SLOTS']=C.response_slots(C.parse_openapi(str(ROOT/'tools/openapi.json'))); n['vars']['products_raw']=[dict(product_id='p1',type='credit_card',card_last4='1234',past_due_amount=420,days_late=5,minimum_payment=100)]
# Use the actual API response slot names, then initialize normally.
a=n['SLOTS']['account']; n['vars']['products_raw']=[{a['id']:'p1',a['type']:'credit_card',a['card_last4']:'1234',a['past_due']:420,a['days_late']:5,'minimum_payment':100}]
n['st_init_products']()
n['vars']['cust_intent']='too_much';n['_run']('neg_route')
out['expired_window']={'offer':n['_S']()['offer'],'instruction':n['vars']['neg_instruction']}
n['vars']['cust_intent']='accepts';n['_run']('neg_route');out['expired_window']['accepted_product']=n['_S']()['products'][0];out['expired_window']['next']=n['vars']['next']
n['vars']['rb_intent']='confirms';n['_run']('readback_route');n['st_write_step']();out['expired_window']['write']={k:n['vars'].get(k) for k in ('next','w_amount','w_date','w_product_id')}
d=copy.deepcopy(base);d['bands'][0]['deadline']={'kind':'earliest','rules':[{'kind':'day_of_month','day':40,'adjustment':'following'}, {'kind':'nth_business_day','n':2}]}
out['invalid_composite']={'validation':P.validate(P.PolicyIR.from_dict(d)), 'deadline':bc.deadline('2026-10-14',d['bands'][0]['deadline'],[],[0,1,2,3,4])}
n,s,p=env();s.update(rb_idle=5);n['_save'](s);n['vars']['rb_intent']='other';n['_run']('readback_route');out['sixth_readback_idle']={'next':n['vars']['next'],'product':n['_S']()['products'][0]}
n,s,p=env();n['vars'].update(prop_kind='weekday',prop_weekday='tuesday',prop_relative='next');out['explicit_next_weekday']=n['_resolve_date']('prop','2026-10-14','2026-10-27')
out['month_boundaries']=[]
for today,rule in [('2028-01-31',dict(kind='day_of_month',day=31,month_offset=1,adjustment='none')),('2026-12-31',dict(kind='day_of_month',day=1,month_offset=1,adjustment='following')),('2026-10-31',dict(kind='end_of_month',basis='calendar',adjustment='following'))]:
 out['month_boundaries'].append(dict(today=today,rule=rule,result=bc.deadline(today,rule,['2027-01-01'],[0,1,2,3,4])))
old=subprocess.check_output(['git','show','70ce3b4:workflow_runtime.py'],cwd=ROOT,text=True)
n,s,p=env();exec(old,n);n['vars'].update(prop_kind='weekday',prop_weekday='tuesday',prop_relative='next');out['v23_explicit_next_weekday']=n['_resolve_date']('prop','2026-10-14','2026-10-27')
n,s,p=env();exec(old,n);s['rb_idle']=5;n['_save'](s);n['vars']['rb_intent']='other';n['_run']('readback_route');out['v23_sixth_idle']={k:n['vars'].get(k) for k in ('next','neg_instruction')}
print(json.dumps(out,indent=2))
