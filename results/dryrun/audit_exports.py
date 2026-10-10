"""Read exported workflows and evaluate predeclared brief requirements offline."""
import ast,datetime,hashlib,importlib.util,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2];ev=root/'results/dryrun'
sys.path.insert(0,str(root));import bankcal
expect=json.loads((ev/'expected-before-build.json').read_text());reports={}
def strings(x,path=''):
 if isinstance(x,str):yield path,x
 elif isinstance(x,dict):
  for k,v in x.items():yield from strings(v,path+'.'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from strings(v,path+f'[{i}]')
def independent(day,rule,holidays):
 d=datetime.date.fromisoformat(day);business=lambda x:x.weekday()<5 and x.isoformat() not in holidays
 if rule['kind']=='nth_business_day':
  left=rule['n']
  while left:
   d+=datetime.timedelta(days=1)
   if business(d):left-=1
 elif rule['kind']=='calendar_days':d+=datetime.timedelta(days=rule['n'])
 elif rule['kind']=='end_of_month':d=(d.replace(day=28)+datetime.timedelta(days=4)).replace(day=1)-datetime.timedelta(days=1)
 else:raise ValueError(rule)
 direction=rule.get('adjustment','none')
 if direction!='none':
  while not business(d):d+=datetime.timedelta(days=1 if direction=='following' else -1)
 return d.isoformat()
for index,folder in enumerate(['dry-1','dry-2'],1):
 slot=f'hidden-{index}';e=expect[folder];export=json.loads((root/'out'/f'{slot}.workflow.json').read_text());wf=export['workflow'];raw=json.loads((root/'out'/f'{slot}.policy.json').read_text());audit=json.loads((root/'out'/f'{slot}.audit.json').read_text());api=json.loads((root/'hidden'/folder/'openapi.json').read_text())
 checks=[]
 def check(path,want,actual,note=''):
  checks.append({'path':path,'expected':want,'actual':actual,'match':want==actual,'note':note})
 policies=[];sources={};embedded_slots=[]
 for name,n in wf['nodes'].items():
  for loc,s in strings(n):
   if 'POLICY = json.loads(' not in s:continue
   tree=ast.parse(s);sources[name]=s
   for a in tree.body:
    if isinstance(a,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='POLICY' for t in a.targets):policies.append((name,json.loads(ast.literal_eval(a.value.args[0]))))
    if isinstance(a,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SLOTS' for t in a.targets):embedded_slots.append((name,json.loads(ast.literal_eval(a.value.args[0]))))
 assert policies,'No embedded policy found'
 policy=policies[0][1]
 check('all_code_nodes_same_policy',True,all(p==policy for _,p in policies))
 check('bank_name',e['bank'],policy['bank_name'])
 slots=embedded_slots[0][1]
 for section,values in {'verify':{'ok':'operation_success','verified':'check_passed','all_verified':'all_checks_complete','remaining':'remaining_tries'},'account':{'list':'obligations','id':'facility_id','type':'product_type','past_due':'outstanding_amount','days_late':'days_past_due'}}.items():
  for k,want in values.items():check('SLOTS.'+section+'.'+k,want,slots[section].get(k))
 for tool,flag in slots['ok_by_tool'].items():check('SLOTS.ok_by_tool.'+tool,'operation_success',flag)
 check('identity.order',[x['field'] for x in e['identity']],[x['field'] for x in policy['identity']['requirements']])
 def namespace(name,variables=None):
  tree=ast.parse(sources[name])
  tree.body=[n for n in tree.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_run')]
  assert all(all(a.name in ['json','re','datetime'] for a in n.names) for n in tree.body if isinstance(n,ast.Import))
  ns={'vars':variables or {'now':'2026-10-14T11:00'}};exec(compile(tree,'exported-'+name,'exec'),ns);return ns
 question_ns=namespace('opening_route')
 sample={'facility_id':'offline-sample','product_type':e['types'][0],'outstanding_amount':987.65,'days_past_due':13,e['floors'][0]:5}
 account_ns=namespace('init_products',{'now':'2026-10-14T11:00','products_raw':json.dumps([sample])})
 account_ns['_run']('init_products')
 account_state=json.loads(account_ns['vars'].get('state_json','{}'))
 check('runtime.account.full_amount',987.65,(account_state.get('products') or [{}])[0].get('full'),note='Executed exported init_products with offline API-shaped sample: outstanding_amount=987.65, days_past_due=13, floor=5; no bank request.')

 for i,item in enumerate(e['identity']):
  actual=policy['identity']['requirements'][i] if i<len(policy['identity']['requirements']) else {}
  for field in ['field','ask_text','answer_format','digits']:check(f'identity[{i}].{field}',item[field],actual.get(field))
  if item['answer_format']=='date':check(f'identity[{i}].numeric_date_order','mdy',actual.get('numeric_date_order'))
  node=wf['nodes'].get('ask_'+str(i),{});text='\n'.join(v for _,v in strings({k:node.get(k) for k in ['on_enter','task_message']}))
  rendered=question_ns['_ask_text'](i)
  check(f'ask_{i}.question_present',True,item['ask_text'] in rendered and node.get('on_enter',{}).get('text')=='{{id_say}}',note='Actual node speaks id_say; evaluated exported _ask_text(i): '+rendered)
  verify_ns=namespace('verify_after_'+str(i),{'now':'2026-10-14T11:00','v_ok':'true','v_verified':'true','v_all':'false'})
  verify_ns['_run']('verify_after_'+str(i))
  check(f'verify_after_{i}.next','get_account' if i==len(e['identity'])-1 else 'ask_'+str(i+1),verify_ns['vars'].get('next'))
  verify=wf['nodes'].get('verify_'+str(i),{})
  defaults=[v for k,v in strings(verify) if k.endswith('.field.default')]
  check(f'verify_{i}.field',[item['field']],defaults)
 for path,want in {'identity.wrong_answer_limit':e['limit'],'identity.remaining_slot':'remaining_tries','identity.asking_purpose_counts_as_decline':False,'identity.failed_instruction':'Please contact the verification desk.','identity.holder_confirmation_asks':2,'third_party.callback.days':e['callback'][0],'third_party.callback.start':e['callback'][1],'third_party.callback.end':e['callback'][2],'third_party.deceased_sentence':'We are sorry for your loss.','calendar.holidays':e['holidays'],'calendar.business_days':[0,1,2,3,4],'calendar.missing_date_parts':'next_occurrence','calendar.next_weekday_means_following_week':True,'multi_product.max_products':e['max_products'],'amounts.floors':dict(zip(e['types'],e['floors'])),'promise_write.retry_on_failure':e['retry'],'promise_write.confirm_phrase':'May I save this payment agreement?','amounts.floor_wording':'The unpaid remainder remains overdue.','notes.enabled':True,'notes.none_on_transfer':True,'outcomes.transfer_overrides_promise':True,'phrases.opening_verbatim':True}.items():
  actual=policy
  for part in path.split('.'):actual=actual.get(part) if isinstance(actual,dict) else None
  check(path,want,actual)
 for name,item in [('human',{'ask_once_first':index==1}),('already_paid',{'ends_call':False,'action':{'type':'note','reason':e['reasons']['settled']}}),('dispute',{'ends_call':False,'action':{'type':'note','reason':e['reasons']['disputed']}}),('hardship',{'ends_call':False,'offer_transfer_queue':e['queues']['care']})]:
  sc=next((s for s in policy['special_cases'] if s['name']==name),{})
  for k,want in item.items():check('special_cases.'+name+'.'+k,want,sc.get(k))
 for k,want in e['phrases'].items():
  actual=policy['phrases'].get(k,'').replace('<<','{{').replace('>>','}}');check('phrases.'+k,want,actual)
 check('opening.on_enter',True,e['phrases']['opening'] in json.dumps(wf['nodes']['opening'].get('on_enter',{})))
 if index==2:
  for node,values in [('opening_route',{'holder':'wants_human'}),('id_route_0',{'id_intent':'wants_human'})]:
   ns=namespace(node,{'now':'2026-10-14T11:00',**values});ns['_run'](node)
   check('memo.immediate_human.'+node,'transfer',ns['vars'].get('next'),note='Executed exported Python only, with preclassified intent; no chat or bank requests.')
 code_table={r['outcome']:sorted(r['reasons']) for r in policy['outcomes']['table']}
 check('outcomes.table',{k:sorted(v) for k,v in e['table'].items()},code_table)
 close_nodes={}
 def request(n):return api['paths']['/bank/'+n]['post']['requestBody']['content']['application/json']['schema']['properties']
 for name,n in wf['nodes'].items():
  for pa in n.get('pre_actions',[]):
   fn=pa.get('function',{})
   if fn.get('name')!='close_call':continue
   props=fn['parameters']['properties'];body=props['body']['properties'];close_nodes[name]=body
   check(name+'.url',api['servers'][0]['url']+'/bank/close_call',props['url']['default'])
   for fld in ['outcome','reason']:
    if fld=='reason' and fld not in body:continue
    check(name+'.'+fld+'.enum',sorted(request('close_call')[fld]['enum']),sorted(body.get(fld,{}).get('enum',[])))
    check(name+'.'+fld+'.default','{{final_'+fld+'}}',body.get(fld,{}).get('default'))
   check(name+'.success_mapping',True,any(m.get('path')=='data.operation_success' for m in n.get('response_mapping',[])))
 check('close_noreason.omits_reason',True,'reason' not in close_nodes.get('close_noreason',{}))
 for name in ['failed_outcome','declined_outcome','unclear_holder_outcome']:
  outcome,reason=policy['identity'][name];check('identity.'+name+'.allowed_pair',True,outcome in e['table'] and reason in e['table'][outcome])
 for sc in policy['special_cases']:
  a=sc.get('action',{})
  if a.get('type') in ['close','transfer']:
   o,r=a.get('outcome'),a.get('reason','');check('special_cases.'+sc['name']+'.allowed_pair',True,o in e['table'] and (r in e['table'][o] if e['table'][o] else not r))
 deadlines=[]
 for i,b in enumerate(e['bands']):
  actual=next((x for x in policy['bands'] if x['days_late_min']==b['days_late_min'] and x['days_late_max']==b['days_late_max']),{})
  check(f'bands[{i}].deadline',b['deadline'],actual.get('deadline'))
  check(f'bands[{i}].attempts',[{'amount':'full','date':'deadline','floor_if_full_refused':True}],actual.get('attempts'))
  for now in ['2026-10-14','2026-10-23','2026-11-25','2026-12-24']:
   want=independent(now,b['deadline'],e['holidays']);got=bankcal.deadline(now,actual.get('deadline',{}),policy['calendar']['holidays'],policy['calendar']['business_days'])
   check(f'deadline[{i}]@{now}',want,got)
   deadlines.append({'band':[b['days_late_min'],b['days_late_max']],'now':now,'expected':want,'actual':got})
 # Verify the actual exported Python calendar function implementations agree with the pinned bankcal source.
 bankdefs={n.name:ast.dump(n,include_attributes=False) for n in ast.parse((root/'bankcal.py').read_text()).body if isinstance(n,ast.FunctionDef)}
 # Source minification drops docstrings. Compare without docstrings on both sides.
 def normalized(n):
  if n.body and isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Constant) and isinstance(n.body[0].value.value,str):n.body.pop(0)
  return ast.dump(n,include_attributes=False)
 bankdefs={n.name:normalized(n) for n in ast.parse((root/'bankcal.py').read_text()).body if isinstance(n,ast.FunctionDef)}
 for name,src in sources.items():
  for fn in ast.parse(src).body:
   if isinstance(fn,ast.FunctionDef) and fn.name=='deadline':check(name+'.embedded_deadline_matches_source',bankdefs['deadline'],normalized(fn))
 report={'slot':slot,'folder':folder,'workflow_id':export['workflow_id'],'nodes':len(wf['nodes']),'checks':checks,'mismatches':[c for c in checks if not c['match']],'deadlines':deadlines,'unresolved':raw.get('unresolved',[]),'audit_unresolved':audit.get('unresolved',[]),'audit_fixed':audit.get('fixed',[]),'close_nodes':close_nodes,'embedded_policy':policy}
 reports[slot]=report
 print(slot,len(checks),'checks',len(report['mismatches']),'mismatches',flush=True)
 for c in report['mismatches']:print(json.dumps(c),flush=True)
(ev/'workflow-audit.json').write_text(json.dumps(reports,indent=2))
