"""Independent fixture-to-HTTP comparison. Does not import or alter mock implementation."""
import collections, hashlib, json, pathlib, time, urllib.request, urllib.error
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parents[3]
OUT=pathlib.Path(__file__).resolve().parent/'post-redeploy'
OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'hidden/final/test-environment/test-customers.json'
BASE='https://yapmak-bank-mock.winter-mountain-4405.workers.dev'
raw=SOURCE.read_bytes()
fixture=json.loads(raw)
ROUTES={'cards.list': '/voice/v1/cards.list', 'cards.balance': '/voice/v1/cards.balance', 'statement.week.get': '/voice/v1/statement.week.get', 'statement.week.decide': '/voice/v1/statement.week.decide', 'statement.week.change': '/voice/v1/statement.week.change', 'contact.email.get': '/voice/v1/contact.email.get', 'statement.pdf.send': '/voice/v1/statement.pdf.send'}
def leaves(value,keys=()):
    if 'http' in value:
        yield keys,value
    else:
        for k,v in value.items(): yield from leaves(v,keys+(k,))
def diff(expected,actual,path='$'):
    if isinstance(expected,(int,float)) and not isinstance(expected,bool) and isinstance(actual,(int,float)) and not isinstance(actual,bool):
        return [] if expected==actual else [{'path':path,'expected':expected,'actual':actual}]
    if type(expected)!=type(actual):return [{'path':path,'expected':expected,'actual':actual}]
    if isinstance(expected,dict):
        out=[]
        for k in sorted(expected.keys()|actual.keys()):
            if k not in expected or k not in actual:out.append({'path':path+'.'+k,'expected':expected.get(k,'<missing>'),'actual':actual.get(k,'<missing>')})
            else:out.extend(diff(expected[k],actual[k],path+'.'+k))
        return out
    if isinstance(expected,list):
        if len(expected)!=len(actual):return [{'path':path,'expected':expected,'actual':actual}]
        return [d for i,(e,a) in enumerate(zip(expected,actual)) for d in diff(e,a,f'{path}[{i}]')]
    return [] if expected==actual else [{'path':path,'expected':expected,'actual':actual}]
cases=[]
for c in fixture['customers']:
    listed={x['cardNumber'] for x in c['services']['cards.list']['response'].get('data',{}).get('cards',[])}
    for service,value in c['services'].items():
        assert service in ROUTES,service
        for keys,entry in leaves(value):
            request={'customerNo':str(c['customerNo'])}
            if keys:
                assert keys[0] in listed or c['services']['cards.list']['http'] != 200,(c['customerNo'],keys)
                request['cardNumber']=keys[0]
            if len(keys)>1:request['newStatementWeek']=keys[1]
            assert len(keys)<=2
            cases.append((service,request,entry))
start=datetime.now(timezone.utc).isoformat()
rows=[]
with (OUT/'responses.jsonl').open('w') as evidence:
    for i,(service,body,entry) in enumerate(cases,1):
        req=urllib.request.Request(BASE+ROUTES[service],data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'yapmak-independent-fixture-verification/1.0'},method='POST')
        row={'case':i,'time':datetime.now(timezone.utc).isoformat(),'service':service,'path':ROUTES[service],'request':body,'expected_http':entry['http'],'expected_response':entry['response']}
        t=time.monotonic()
        try:
            try: response=urllib.request.urlopen(req,timeout=max(35,entry.get('delaySeconds',0)+20))
            except urllib.error.HTTPError as e:response=e
            with response:
                row['actual_http']=response.status
                text=response.read().decode('utf-8')
            try:actual=json.loads(text)
            except ValueError:actual=text
            row['actual_response']=actual
            row['body_differences']=diff(entry['response'],actual)
            row['match']=response.status==entry['http'] and not row['body_differences']
        except Exception as e:
            row.update(match=False,transport_error=type(e).__name__+': '+str(e))
        row['duration_seconds']=round(time.monotonic()-t,3)
        if entry.get('delaySeconds') or entry.get('gecikmeSaniye'):row['expected_delay_seconds']=entry.get('delaySeconds',entry.get('gecikmeSaniye'))
        evidence.write(json.dumps(row,ensure_ascii=False)+'\n');evidence.flush();rows.append(row)
        if i%25==0 or not row['match']:print(f"{i}/{len(cases)} complete; mismatches={sum(not r['match'] for r in rows)}",flush=True)
        time.sleep(0.10)
summary={'base_url':BASE,'source':str(SOURCE.relative_to(ROOT)),'source_sha256':hashlib.sha256(raw).hexdigest(),'source_unchanged':SOURCE.read_bytes()==raw,'started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),'customers':len(fixture['customers']),'cards':sum(len(c['services']['cards.list']['response'].get('data',{}).get('cards',[])) for c in fixture['customers']),'cases':len(rows),'matched':sum(r['match'] for r in rows),'mismatches':sum(not r['match'] for r in rows),'by_service':dict(collections.Counter(r['service'] for r in rows)),'expected_non_200':sum(r['expected_http']!=200 for r in rows),'delayed':[{'case':r['case'],'expected_seconds':r['expected_delay_seconds'],'observed_seconds':r['duration_seconds']} for r in rows if 'expected_delay_seconds' in r],'failed_cases':[r['case'] for r in rows if not r['match']]}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2),flush=True)
