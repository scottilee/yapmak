"""Repeat the extraction audit in a NEW output directory; no Freya calls/simulation."""
import argparse, pathlib, shutil, hashlib, json, subprocess, time, concurrent.futures, sys
parser=argparse.ArgumentParser()
parser.add_argument('--out',required=True,help='new directory relative to repository root')
args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[3]
base=(root/args.out).resolve()
base.mkdir(parents=True,exist_ok=False)
snap=base/'snapshot'
files=[*root.glob('*.py'),*root.glob('scripts/*.py'),*root.glob('tools/*.py'),*root.glob('tests/**/*.py'),*root.glob('tests/fixtures/**/*.json')]
files += [root/p for p in ['briefs/brief-a.md','briefs/brief-b.md','tools/openapi.json','public-test-set.json','tests/fixtures/synthetic/clean-eom-brief.md']]
revision={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'status':subprocess.check_output(['git','status','--short'],cwd=root,text=True),'started_epoch':time.time()}
manifest={}
for src in sorted(set(files)):
    rel=src.relative_to(root);dest=snap/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    manifest[str(rel)]=hashlib.sha256(dest.read_bytes()).hexdigest()
if any(hashlib.sha256((root/p).read_bytes()).hexdigest()!=h for p,h in manifest.items()):
    raise RuntimeError('Source changed during snapshot; use another output directory and retry')
(base/'manifest.json').write_text(json.dumps(manifest,indent=2));(base/'revision.json').write_text(json.dumps(revision,indent=2))
for helper in ('compare.py','verify_outputs.py'):
    shutil.copyfile(pathlib.Path(__file__).parent/helper,base/helper)
(base/'findings.md').write_text('Pending reviewer interpretation.\n')
cases=[('a','briefs/brief-a.md','tools/openapi.json'),('ab','briefs/brief-a.md,briefs/brief-b.md','tools/openapi.json'),('clean-eom','tests/fixtures/synthetic/clean-eom-brief.md','tests/fixtures/synthetic/clean-eom-openapi.json')]
def run_group(case):
    name,brief,api=case
    for i in range(1,4):
        slot=f'det-{name}-{i}';start=time.time();print(f'START {slot}',flush=True)
        command=[sys.executable,'-u','extract.py',brief,api,slot]
        error=None
        with (base/f'{slot}.log').open('w') as log:
            try:result=subprocess.run(command,cwd=snap,stdout=log,stderr=subprocess.STDOUT,timeout=1500);code=result.returncode
            except subprocess.TimeoutExpired:code=124;error='Extraction exceeded 1500 seconds'
        record={'slot':slot,'exit_code':code,'duration_s':round(time.time()-start,2),'started_epoch':start,'briefs':brief,'openapi':api,'command':command,'error':error}
        (base/f'{slot}.run.json').write_text(json.dumps(record,indent=2));print('DONE '+json.dumps(record),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run_group,cases))
print('ALL COMPLETE',flush=True)
