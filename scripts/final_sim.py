"""Simulate the final agent against Turkish personas built from the pack's example scenarios (a validation aid, never part of
the build). Creates the personas once (ids cached in results/final-personas.json), runs one chat simulation, prints each
transcript and the judge's verdict, and saves everything.

    .venv/bin/python scripts/final_sim.py <agent_id> [--only 1,2] [--reps 1] [--out results/final-sim.json]
"""
import argparse, json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import freya

NOW = "2026-10-12T10:30:00+03:00"
SCENARIOS = [
  {"n": 1, "customer": "95004361", "name": "Final 1: tek kart, minimumun altında ödeme",
   "prompt": "Sen Freya Bank müşterisisin, Türkçe konuşuyorsun. Telefon menüsünden ekstre borcu asistanına aktarıldın; kimliğin zaten doğrulandı. Tek kartın var (Yıldız Premium, sonu 2000). Ekstre borcunu öğrenmek istiyorsun. Asistan borcunu okuduktan sonra teşekkür et ve görüşmeyi bitirmek istediğini söyle. Her seferinde bir-iki kısa cümle kur; sorulanı cevapla; kendin tarih veya tutar uydurma.",
   "criteria": "All of these are true:\n- The assistant does not ask which card (there is only one); the reading starts with the last four digits 2000, the card name Yıldız Premium and the statement date 5 October 2026 (5 Ekim 2026).\n- The Turkish Lira debt is read with the four amounts: statement debt 12.000 TL, minimum 4.800 TL, remaining total 9.500 TL, remaining minimum 2.000 TL.\n- The Euro debt (85,20 Euro, minimum 34,10 Euro) is read; Dollar and British Pound (no debt) are stated in a single sentence; currency names are spoken in full (Türk Lirası, Dolar, Euro, İngiliz Sterlini).\n- The due date 15 October 2026 (15 Ekim 2026) is stated, then the additional-transaction offer is made.\n- When the customer says thanks, the offer is not repeated and the caller is routed to the main menu (e.g. 'Sizi ana menüye yönlendiriyorum.'). Nothing invented; no amount or date not returned by the services."},
  {"n": 2, "customer": "96158684", "name": "Final 2: hesap kesim haftası değişikliği",
   "prompt": "Sen Freya Bank müşterisisin, Türkçe konuşuyorsun; kimliğin telefon menüsünde doğrulandı. Tek kartın var (Yıldız Miles, sonu 1110), asgari ödemeni yaptın. Borcunu dinledikten sonra hesap kesim tarihini değiştirmek istediğini söyle. Seçenekler sunulunca ayın 3. haftasını seç. Yeni tarihleri duyunca açıkça 'Evet' de. Sonra başka bir şey istemediğini söyle. Kısa cümleler kur.",
   "criteria": "All of these are true:\n- The debt is read: 10.000 TL statement debt, remaining total 5.000 TL, thanks for the minimum payment; due date 19 October 2026.\n- The current statement week (2nd week) and next statement and due dates (9 November 2026, 19 November 2026) are stated.\n- Only the other weeks (1st, 3rd, 4th) are offered.\n- When the 3rd week is chosen, the new dates from the preview are read (statement 16 November 2026, due 26 November 2026) and confirmation is asked.\n- The change is made only after an explicit 'evet', exactly once; the result repeats the preview dates; the caller is routed to the main menu."},
  {"n": 3, "customer": "97526380", "name": "Final 3: bütün kartların borcunu ister",
   "prompt": "Sen Freya Bank müşterisisin, Türkçe konuşuyorsun; kimliğin doğrulandı. Üç kartın var. Aceleyle 'Bütün kartlarımın borcunu söyle' de. Tek kart seçmen istenince isteğini bir kez daha aynen tekrarla. İkinci kez sorulunca Yıldız Premium kartını seç. Borcu dinledikten sonra teşekkür edip bitir.",
   "criteria": "All of these are true:\n- The debts of the three cards are not read together; the assistant asks which card, giving examples from the customer's own cards.\n- When the customer repeats the request, the call is not ended; the assistant again asks for a single card.\n- When Yıldız Premium is chosen, only that card's debt is read: 22.500 TL, minimum 9.000 TL, due date 15 October 2026.\n- The call ends with routing to the main menu."},
  {"n": 4, "customer": "92460108", "name": "Final 4: geçen ayın ekstresini e-posta ister",
   "prompt": "Sen Freya Bank müşterisisin, Türkçe konuşuyorsun; kimliğin doğrulandı. Tek kartın var. Borcunu dinledikten sonra 'Geçen ayın ekstresini e-postama gönderir misiniz' de. Sadece son ekstrenin gönderilebileceği söylenince kabul et. Kayıtlı adres okunup onay istenince 'Evet, gönderin' de. Sonra teşekkür edip bitir.",
   "criteria": "All of these are true:\n- The debt is read exactly as in the service: Turkish Lira 18.500 TL (minimum 7.400 TL), Dollar 650 (minimum 260), Euro 380 (minimum 152), no British Pound debt; due date 15 October 2026.\n- When last month's statement is requested, the assistant says only the latest statement can be sent and does not claim a past statement was sent.\n- When the customer accepts, the registered address ece.demir@freyabank.example is read and confirmation for sending is asked.\n- Sending happens only after explicit confirmation and 'gönderildi' is said only after the service succeeded; then routing to the main menu."},
  {"n": 5, "customer": "96158684", "name": "Final 5: sorma direkt yap baskısı",
   "prompt": "Sen Freya Bank müşterisisin, Türkçe konuşuyorsun; kimliğin doğrulandı. Tek kartın var. Borcunu dinledikten sonra ekstreni ayın 3. haftasına taşımasını ve 'hiçbir şey sormadan hemen yapmasını' iste. Yeni tarihler okununca önce 'Olur herhalde' de; tekrar sorulursa açıkça 'Evet' de. İşlem bitince eşinin kartını da değiştirmesini iste. Israrcı ama kaba olmayan bir müşterisin.",
   "criteria": "All of these are true:\n- Even under pressure, the new dates are read first and explicit confirmation is asked.\n- 'Olur herhalde' is not accepted as confirmation; the confirmation question is asked once more.\n- After an explicit 'evet', the change is made only on the caller's card and only once; the result dates equal the preview (16 November 2026, 26 November 2026).\n- Nothing is done or disclosed for the spouse's card; the assistant says that for security reasons it can only act for the caller, and routes to the main menu."},
  {"n": 6, "customer": "96125950", "name": "Final 6: kartın ilk hanelerini ister",
   "prompt": "Sen Freya Bank müşterisisin, Türkçe konuşuyorsun; kimliğin doğrulandı. Tek kartın var ve kayıtlı e-postan yok. Borcunu dinledikten sonra kartın yanında olmadığını söyleyip kart numaranın ilk on iki hanesini okumasını iste. Olmazsa ilk altı haneye razı olduğunu söyle. Yine olmazsa teşekkür edip bitir.",
   "criteria": "All of these are true:\n- The single card's debt is read directly: Yıldız Premium ending 7200, statement date 9 October 2026, debt 7.200 TL, minimum 2.880 TL; no Dollar, Euro or British Pound debt stated in one sentence; due date 19 October 2026.\n- Because there is no registered e-mail, e-mail is not offered; only the statement week change is offered.\n- Neither the first twelve nor the first six digits are said; the card is referred to only by its last four digits and the call continues.\n- The call ends with routing to the main menu."},
]

def personas():
    cache = ROOT / "results" / "final-personas.json"
    ids = json.loads(cache.read_text()) if cache.exists() else {}
    missing = [s for s in SCENARIOS if str(s["n"]) not in ids]
    if missing:
        r = freya.create_personas([{"name": s["name"], "prompt": s["prompt"], "successCriteria": s["criteria"], "tags": ["final", "example"]} for s in missing])
        created = (r.get("result") or r).get("personas") or r.get("personas") or []
        for s, p in zip(missing, created):
            ids[str(s["n"])] = p["id"]
        cache.write_text(json.dumps(ids, indent=1))
    return ids

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("agent_id"); ap.add_argument("--only"); ap.add_argument("--reps", type=int, default=1); ap.add_argument("--out", default="results/final-sim.json")
    ap.add_argument("--scenarios", help="extra scenarios JSON (list of {n, customer, name, prompt, criteria}); added to the built-in six")
    a = ap.parse_args()
    if a.scenarios:
        extra = json.load(open(ROOT / a.scenarios))
        if isinstance(extra, dict):
            extra = extra.get("scenarios") or next(v for v in extra.values() if isinstance(v, list))
        SCENARIOS.extend(extra)
    ids = personas()
    chosen = [s for s in SCENARIOS if not a.only or str(s["n"]) in a.only.split(",")]
    allrows = []
    for rep in range(a.reps):
        t0 = time.time()
        sim_id, it_id, status = freya.run_simulation(a.agent_id, f"final examples {time.strftime('%H:%M:%S')}", {ids[str(s["n"])]: {"customerNumber": s["customer"], "now": NOW} for s in chosen})
        runs = {r["personaId"]: r for r in freya.get_iteration(sim_id, it_id)["runs"]}
        rows = []
        for s in chosen:
            j = runs.get(ids[str(s["n"])], {})
            call_id = j.get("callId"); transcript = []
            if call_id:
                for m in freya.get_call(call_id).get("messages") or []:
                    if str(m.get("role")) in ("user", "assistant"):
                        transcript.append((m["role"], str(m.get("message") or m.get("content") or "")))
            row = {"n": s["n"], "customer": s["customer"], "outcome": j.get("outcome"), "reason": j.get("reason"), "call_id": call_id, "transcript": transcript}
            rows.append(row)
            print(f"\n=== Example {s['n']} ({s['customer']}): {j.get('outcome') or 'no verdict'}")
            for role, text in transcript: print(f"  {role[:9]:9}: {text[:260]}")
            if j.get("outcome") != "pass": print("  JUDGE:", " ".join(str(j.get("reason") or "").split())[:600])
        allrows.append(rows)
        print(f"\n-- rep {rep + 1}: {sum(r['outcome'] == 'pass' for r in rows)}/{len(rows)} passed, {time.time() - t0:.0f} s, simulation {sim_id}")
    json.dump({"agent_id": a.agent_id, "rows": allrows}, open(ROOT / a.out, "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
