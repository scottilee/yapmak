"""Run existing extract -> compile -> publish_check CLIs, preserving stage evidence.

Use --extract-only for independent extraction work; --finish resumes compile and
publication. Serialize --finish calls: both fixtures reuse generalization-check.
"""
import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('fixture',choices=['clean-eom','reversal-thread'])
    ap.add_argument('--extract-only',action='store_true')
    ap.add_argument('--finish',action='store_true')
    args=ap.parse_args()
    fixture=args.fixture
    prefix='probe-'+fixture+'-v2'
    out=ROOT/'results/generalization'/fixture/'consistent-input-run'
    out.mkdir(parents=True,exist_ok=True)
    summary_path=out/'pipeline.json'
    summary=json.loads(summary_path.read_text()) if args.finish and summary_path.exists() else {
        'fixture':fixture,'prefix':prefix,'scratch_slot':'generalization-check','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stages':[]}
    def save(): summary_path.write_text(json.dumps(summary,indent=2)+'\n')
    def run(name,cmd,timeout):
        t=time.monotonic()
        log=out/(name+'.log')
        hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('extract.py','compile.py','policy.py','scripts/publish_check.py')}
        with log.open('w') as stream:
            try:
                proc=subprocess.run([str(ROOT/'.venv/bin/python'),'-u']+cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
                code=proc.returncode
            except subprocess.TimeoutExpired:
                code=124
        # Match existing trace redaction; never expose credentials in reports.
        text=log.read_text()
        for key in ('FREYA_API_KEY','FREYA_BANK_TEAM_KEY','ANTHROPIC_API_KEY'):
            if os.environ.get(key): text=text.replace(os.environ[key],'[REDACTED]')
        log.write_text(text)
        stage={'name':name,'command':['.venv/bin/python','-u']+cmd,'exit_code':code,'elapsed_s':round(time.monotonic()-t,2),'implementation_hashes':hashes}
        summary['stages'].append(stage); save()
        print(json.dumps(stage),flush=True)
        return code
    base='tests/fixtures/synthetic/'+fixture
    if not args.finish:
        inputs={}
        for suffix in ('-brief.md','-openapi.json','-expected.json'):
            p=ROOT/(base+suffix)
            inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
            shutil.copyfile(p,out/p.name)
        summary['input_hashes']=inputs; save()
        run('extract',['extract.py',base+'-brief.md',base+'-openapi.json',prefix],1350)
    for suffix in ('.policy.json','.audit.json'):
        p=ROOT/'out'/(prefix+suffix)
        if p.exists(): shutil.copyfile(p,out/p.name)
    trace=ROOT/'traces'/(prefix+'.extract.jsonl')
    if trace.exists(): shutil.copyfile(trace,out/'extract.trace.jsonl')
    if args.extract_only: return
    extraction=next((s for s in reversed(summary['stages']) if s['name']=='extract'),None)
    if not extraction or extraction['exit_code']!=0:
        summary['blocked']='Extraction did not complete successfully; downstream stages not run.'; save(); return
    policy_path='out/'+prefix+'.policy.json'
    run('ir-diff',['scripts/check_synthetic_ir.py',fixture,policy_path,str((out/'ir-diff.json').relative_to(ROOT))],30)
    wf='out/'+prefix+'.workflow.json'
    code=run('compile',['compile.py',policy_path,base+'-openapi.json',wf],90)
    if (ROOT/wf).exists(): shutil.copyfile(ROOT/wf,out/'candidate.workflow.json')
    if code!=0:
        summary['blocked']='Compilation/static checks failed; no publication of an invalid candidate.'; save(); return
    run('publish-check',['scripts/publish_check.py','generalization-check',wf],360)
    exported=ROOT/'out/generalization-check.export.json'
    log=(out/'publish-check.log').read_text()
    if 'checkpoint exported to' in log and exported.exists():
        shutil.copyfile(exported,out/'published.export.json')
    for line in log.splitlines():
        if line.startswith('published '):
            try: summary['published_ids']=ast.literal_eval(line[len('published '):].rsplit(' (',1)[0])
            except (SyntaxError,ValueError): pass
    summary['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat(); save()


if __name__=='__main__': main()
