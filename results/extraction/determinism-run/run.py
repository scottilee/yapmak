import pathlib, shutil, hashlib, json, subprocess, time, concurrent.futures
root=pathlib.Path.cwd(); base=root/'results/extraction/determinism-run'; snap=base/'snapshot'
files=['extract.py','compile.py','policy.py','bankcal.py','trace.py','briefs/brief-a.md','briefs/brief-b.md','tools/openapi.json','tests/fixtures/synthetic/clean-eom-brief.md','tests/fixtures/synthetic/clean-eom-openapi.json']
manifest={}
for f in files:
 p=snap/f;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/f,p);manifest[f]=hashlib.sha256(p.read_bytes()).hexdigest()
(base/'manifest.json').write_text(json.dumps(manifest,indent=2))
cases=[('a','briefs/brief-a.md','tools/openapi.json'),('ab','briefs/brief-a.md,briefs/brief-b.md','tools/openapi.json'),('clean-eom','tests/fixtures/synthetic/clean-eom-brief.md','tests/fixtures/synthetic/clean-eom-openapi.json')]
def run_group(case):
 name,brief,api=case
 for i in range(1,4):
  slot=f'det-{name}-{i}';start=time.time();print('START',slot,flush=True)
  with (base/f'{slot}.log').open('w') as log:
   p=subprocess.run([str(root/'.venv/bin/python'),'-u','extract.py',brief,api,slot],cwd=snap,stdout=log,stderr=subprocess.STDOUT)
  record={'slot':slot,'exit_code':p.returncode,'duration_s':round(time.time()-start,2),'started_epoch':start,'briefs':brief,'openapi':api}
  (base/f'{slot}.run.json').write_text(json.dumps(record,indent=2));print('DONE',record,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run_group,cases))
print('ALL COMPLETE',flush=True)
