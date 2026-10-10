import concurrent.futures,json,pathlib,sys,shutil,time
sys.path.insert(0,str(pathlib.Path.cwd()/'scripts'))
import intent_chat_checks as checks
out=pathlib.Path('results/extraction/20261010T144657Z-priority').resolve()
results=json.loads((out/'results.json').read_text());done={r['id'] for r in results if r['status']=='completed'}
cases=[c for c in json.loads((out/'selected-cases.json').read_text()) if c['id'] not in done]
schemas=json.loads((out/'schemas.json').read_text());start=time.monotonic()
for group in checks.GROUPS:
 subset=[c for c in cases if c['group']==group]
 if not subset:continue
 pub=out/('retry-published-'+group);pub.mkdir(exist_ok=True)
 ids=checks.publish(checks.workflow(group,schemas[group]),pub)
 for c in subset:
  archive=out/'failed-attempts'/c['id'];archive.mkdir(parents=True,exist_ok=True)
  for p in (out/'calls').glob(c['id']+'.*'):shutil.copy2(p,archive/p.name)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for r in pool.map(lambda c:checks.run_case(ids,c,out),subset):
   results.append(r);checks.save_json(out/'results.json',results)
   print(json.dumps({k:r[k] for k in ['id','status','actual','error'] if k in r}),flush=True)
checks.save_json(out/'retry-completion.json',{'duration_s':round(time.monotonic()-start,2),'completed_unique':len({r['id'] for r in results if r['status']=='completed'}),'attempts':len(results)})
