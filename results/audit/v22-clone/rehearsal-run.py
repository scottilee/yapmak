import subprocess,time,json,pathlib,shutil,os
root=pathlib.Path('/Users/sl/sbx/hackathon'); dest=pathlib.Path('/tmp/v22-clone'); evidence=root/'results/audit/v22-clone'
records=[]; start=time.time()
def run(name,cmd,cwd):
 t=time.time()
 with (evidence/(name+'.log')).open('w') as log:
  result=subprocess.run(cmd,cwd=cwd,stdout=log,stderr=subprocess.STDOUT)
 rec={'step':name,'command':cmd,'cwd':str(cwd),'exit_code':result.returncode,'started_epoch':t,'elapsed_s':round(time.time()-t,3)}
 records.append(rec);(evidence/'timings.json').write_text(json.dumps({'started_epoch':start,'elapsed_s':round(time.time()-start,3),'steps':records},indent=2));print(json.dumps(rec),flush=True)
 return result.returncode
if run('clone',['git','clone',str(root),str(dest)],root):raise SystemExit(1)
if run('setup',['bash','-c','uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt'],dest):raise SystemExit(1)
shutil.copy2(root/'.env',dest/'.env');os.chmod(dest/'.env',0o600)
run('preflight',['scripts/preflight.sh','--with-build'],dest)
run('full-ab',['bash','-c','set -a; source .env; set +a; .venv/bin/python -u build.py --briefs briefs/brief-a.md,briefs/brief-b.md --openapi tools/openapi.json --slot rehearsal-ab'],dest)
run('submit-fast',['scripts/submit.sh','hidden/dry-1','hidden/dry-2','--fast'],dest)
print('COMPLETE',flush=True)
