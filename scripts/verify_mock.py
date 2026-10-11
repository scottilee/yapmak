# Replays every entry of hidden/final/test-environment/test-customers.json against the deployed mock and checks the
# contract error codes for unknown customers/cards/weeks. Usage: .venv/bin/python scripts/verify_mock.py <mock_url>
import json, sys, urllib.request, concurrent.futures as cf
BASE = sys.argv[1]
d = json.load(open('hidden/final/test-environment/test-customers.json'))
H = {"Content-Type": "application/json", "User-Agent": "mock-verify/1.0", "Accept": "application/json"}
def call(service, data):
    req = urllib.request.Request(f"{BASE}/voice/v1/{service}", data=json.dumps({"data": data, "call": {"ani": "05001234567", "lang": "tr"}}).encode(), headers=H, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
cases = []
for c in d['customers']:
    cn = c['customerNo']
    for s, v in c['services'].items():
        if 'http' in v: cases.append((s, {"customerNo": cn, "aiFlow": "CardOps", "intAddressInfoType": "E", "cardNumber": "x", "currencyType": "TL", "statementDate": "01.01.2026", "emailAddress": "a@b"} if s != 'cards.list' else {"customerNo": cn, "aiFlow": "CardOps"}, v))
        else:
            for card, w in v.items():
                if 'http' in w: cases.append((s, {"cardNumber": card}, w))
                else:
                    for wk, e in w.items(): cases.append((s, {"cardNumber": card, "newStatementWeek": int(wk), "statementDay": 5}, e))
def run(case):
    s, q, exp = case
    st, body = call(s, q)
    ok = st == exp['http'] and body == exp['response']
    return ok, s, q, st, exp['http'], None if ok else json.dumps(body, ensure_ascii=False)[:200]
with cf.ThreadPoolExecutor(16) as ex: res = list(ex.map(run, cases))
bad = [r for r in res if not r[0]]
print(f"{len(res)-len(bad)}/{len(res)} entries match")
for r in bad: print("MISMATCH", r[1:])
# unknowns and missing fields
checks = [("cards.list", {"customerNo": "11111111", "aiFlow": "CardOps"}, 404, "FB_IVR_CHANNEL_102"),
          ("cards.balance", {"cardNumber": "540000******9999"}, 404, "FB_IVR_CHANNEL_120"),
          ("statement.week.get", {"cardNumber": "540000******9999"}, 404, "FB_IVR_CHANNEL_121"),
          ("statement.week.decide", {"cardNumber": "540000******1234", "newStatementWeek": 1, "statementDay": 5}, 400, "INVALID_ARGUMENTS_ERROR"),
          ("statement.week.change", {"cardNumber": "540000******9999", "newStatementWeek": "2", "statementDay": 5}, 400, "INVALID_ARGUMENTS_ERROR"),
          ("contact.email.get", {"customerNo": 11111111, "intAddressInfoType": "E"}, 400, "INVALID_ARGUMENTS_ERROR"),
          ("statement.pdf.send", {"customerNo": "93821776", "cardNumber": "x", "currencyType": "TL", "statementDate": "x", "emailAddress": "x"}, 404, "FB_IVR_CHANNEL_107"),
          ("cards.balance", {"cardNumber": ""}, 400, "INVALID_ARGUMENTS_ERROR"),
          ("cards.list", {"customerNo": 90000001}, 200, "1"),
          ("statement.week.decide", {"cardNumber": "540000******1234", "newStatementWeek": "3"}, 200, "1"),
          ("cards.list", {"customerNo": "{{customerNumber}}"}, 200, "1")]
for s, q, st, code in checks:
    got, body = call(s, q)
    print("OK " if (got == st and body['result']['returnCode'] == code) else "BAD", s, q, got, body['result']['returnCode'], body['result'].get('type'))
