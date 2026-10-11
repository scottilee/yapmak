# Final dictated-sentence checklist (verbatim Turkish)

Sources and precedence (newest wins): kickoff thread (24–29 Sep 2026) < session transcript (7 Oct) <
8 Oct analysis < 9 Oct recap (Deniz 10:14) < 9 Oct Selin correction (15:02) < 9 Oct Deniz confirmation (17:48).
The 9 Oct emails explicitly override the 8 Oct document ("I haven't had time to put them into the analysis
document yet … Please build to these"). A 9 Oct recap point that Selin later corrects is overridden by the
correction (only the calming-replies count, recap #5 → three).

Templates: [square brackets] are fill-ins. Amounts/dates inside a sentence are spoken per §4.9 rules
(TL → "Türk Lirası" etc., digits one by one, no kuruş when zero), so grepping a workflow for a sentence
should match its fixed skeleton and treat the slots as wildcards. "Verbatim" = the words must not change;
"wording free" = the message is mandated but no sentence is fixed anywhere.

## A. Card finding (flow doc §3)

| # | Sentence | Rule | Winning source (and conflicts) |
|---|---|---|---|
| A1 | `Hangi kartınızın borcunu öğrenmek istersiniz? Örneğin, [kart adı] veya [kart adı] diyebilirsiniz.` | >1 eligible card, none named; max two examples, only this caller's own card names | 8 Oct §3.1; agreed 7 Oct 03:56–04:11 |
| A2 | `[kart adı] isimli birden fazla kartınız var. Kartınızın son dört hanesini söyler misiniz?` | name fits ≥2 cards (twin step a) | 8 Oct §3.2a; 7 Oct 13:17 |
| A3 | `Son dört hanesi [4253] olan birden fazla kartınız var. Kartınızın son altı hanesini söyler misiniz?` | last four also equal (step b); caller's own digits replace 4253 | 8 Oct §3.2b; 7 Oct 14:20; recap #4 |
| A4 | `Son altı hanesi aynı olan birden fazla kartınız var. Kart numaranızı söyler misiniz?` | last six equal too (step c) | 8 Oct §3.2c; 7 Oct 14:37; recap #4 |
| A5 | `Sonu [4253] ile biten kartınıza ait …` | card with empty productName is introduced by last four only | 9 Oct n/a; kickoff Q12 (25 Sep) = 8 Oct §3.3 |
| A6 | `Size şu anda yardımcı olamıyorum. Sizi ana menüye aktarıyorum.` | three tries used up at any question (also "all of them" refusals, §3.3) | 7 Oct 09:18–09:31 ("failure says aktarıyorum"); 8 Oct §8.1; recap #3 |

Never: no "devam… kartınızla" confirmation line after a card is chosen (7 Oct 04:12–04:18, 8 Oct §3.1);
digits the caller gave (4, 6 or 16) are never repeated back (8 Oct §3.3; 7 Oct 14:54–14:58).

## B. Reading the debt (flow doc §4)

| # | Sentence | Rule | Winning source |
|---|---|---|---|
| B1 | `Sonu [son 4 hane] ile biten [kart adı] kartınıza ait [tarih] tarihinde kesilen ekstre Türk Lirası borcunuz …` | every reading opens with card intro; closing date leads the FIRST currency read (foreign if no TL debt); on every card, also the second in one call | 8 Oct §4.2; order agreed 7 Oct 01:45–02:14 |
| B2 | `Türk Lirası borcunuz XXX TL, ödenmesi gereken minimum tutar ZZZ TL'dir.` | nothing paid (remainingMin ≥ min) | 8 Oct §4.3 |
| B3 | `Türk Lirası borcunuz XXX TL, kalan toplam borcunuz YYY TL'dir. Minimum ödemenizi yaptığınız için teşekkür ederiz.` | minimum paid (remainingDebt > 0, remainingMin ≤ 0) | 8 Oct §4.3 |
| B4 | `Türk Lirası borcunuz XXX TL, ödenmesi gereken minimum tutar ZZZ TL, kalan toplam borcunuz YYY TL, kalan minimum ödeme tutarınız TTT TL'dir.` | below-minimum paid | 8 Oct §4.3 |
| B5 | `[Dolar] borcunuz XXX USD, kalan toplam borcunuz YYY USD, ödenmesi gereken minimum tutar ZZZ USD'dir.` | each foreign currency, order Dolar → Euro → İngiliz Sterlini; currency name spoken in full, code never said | 8 Oct §4.4 + §4.9; names mandated 7 Oct 16:46–17:43 |
| B6 | `[Türk Lirası] borcunuz bulunmamaktadır.` and combined forms `X ve Y borcunuz bulunmamaktadır.` / `X, Y ve Z borcunuz bulunmamaktadır.` | one sentence listing ALL no-debt currencies, after the debt lines; 14 combinations per 8 Oct §4.5 table; full names only (never TL/USD/EUR/GBP codes, never "Sterlin" alone, "Euro" not "Avro") | 8 Oct §4.5; 7 Oct 16:46–17:43; recap #6 |
| B7 | `Sonu [son 4 hane] ile biten [kart adı] kartınızın [hesap kesim tarihi] tarihli ekstresinden borcunuz bulunmamaktadır. Gelecek dönemler dahil toplam borcunuz GGG TL'dir. Son ödeme tarihiniz [son ödeme tarihi] olacaktır.` | statementPaymentStatus NO_DEBT (4.7). Future total TL-only per today's sentence; foreign total still open | 8 Oct §4.7 |
| B8 | `Başka bir kartınızın borcunu öğrenmek ister misiniz?` | more than one eligible card, asked BEFORE the offer; yes → selection again | 7 Oct 02:41–03:13; 8 Oct §4.7, §5.1 |
| B9 | `Borçlarınız için son ödeme tarihiniz [son ödeme tarihi]'dir.` | due date, last before the offer; suffix harmonises (26 Ekim'dir) | 8 Oct §4.8; 7 Oct 02:20 |
| B10 | `Borçlarınız için son ödeme tarihiniz bugündür.` | due date is today | 8 Oct §4.8; 7 Oct 02:30–02:39 |
| B11 | `Hesap kesim tarihiniz bugün, ekstreniz saat 00.00 itibarıyla kesilecek.` | calling on the statement-cut day — marked "something like", wording NOT final | 8 Oct §4.10 only |

## C. The offer and the e-mail (flow doc §5–6)

| # | Sentence | Rule | Winning source |
|---|---|---|---|
| C1 | `Hesap kesim tarihinizi değiştirebilirim ya da ekstrenizi kayıtlı mail adresinize gönderebilirim.` | registered e-mail AND change right available; email.get called BEFORE the offer | 8 Oct §5.2 |
| C2 | `Hesap kesim tarihinizi değiştirebilirim.` | no registered e-mail (ibanEmail empty or communicationType Phone) | 8 Oct §5.2; 7 Oct 21:54–22:02; kickoff-thread rule |
| C3 | `Ekstrenizi kayıtlı mail adresinize gönderebilirim.` | change right used this year / not possible | 8 Oct §5.2 |
| C4 | `Bankamızda kayıtlı bir e-posta adresiniz bulunmadığı için ekstrenizi gönderemiyorum.` | caller asks for e-mail although none registered; then week offer if right left, else main menu | 8 Oct §6.1 |
| C5 | `Ekstrenizi [adres] adresine göndermemi ister misiniz?` | go-ahead before sending; short address read as is, long/messy shortened (e.g. `m ile başlayan Gmail adresiniz`), never spelled letter by letter; send only after clear yes, only to the registered address, only the latest statement | kickoff Q3 (25 Sep) = 8 Oct §6.2; 7 Oct 22:04 |
| C6 | `Ekstreniz kayıtlı e-posta adresinize gönderildi.` | success — say ONLY after statement.pdf.send returned success | kickoff Q3 (25 Sep) = 8 Oct §6.4 |
| C7 | `Şu anda işleminizi gerçekleştiremiyorum, sizi müşteri temsilcimize aktarıyorum.` | contact.email.get or statement.pdf.send fails (error, timeout, 404 document-not-found) → agent, never main menu | kickoff Q7 = 8 Oct §6, §8.3; 7 Oct 26:36 |

## D. Statement week change (flow doc §7)

| # | Sentence | Rule | Winning source |
|---|---|---|---|
| D1 | `Hesap kesim tarihinizi yılda bir kez değiştirebilirsiniz.` | optional notice before the week question; also the explanation when the right is already used and the caller asks anyway | 7 Oct 19:27–20:09 (optional; rule = once per CALENDAR year, not IVR's old "ayda bir/yılda üç"); 8 Oct §7 |
| D2 | `[kart adı] kartınızın hesap kesim tarihi her ayın [hafta]. haftası olarak tanımlı. Bir sonraki hesap kesim tarihiniz [tarih], son ödeme tarihiniz [tarih]. Hesap kesim tarihinizi değiştirmek ister misiniz?` | week.get ok → tell and ask; for a joint statement read BOTH cards here (last four, name, week, next dates) | 8 Oct §7.2 |
| D3 | `Hesap kesim tarihinizi ayın 1., 3. ya da 4. haftasına alabilirim. Hangisini tercih edersiniz?` | options = the three weeks ≠ current (example shows a week-2 card); only offered weeks may be chosen, a day/date/current week → re-read options | 8 Oct §7.3 |
| D4 | `Bu değişiklik kartınıza bağlı [bağlı kart adı] kartınızı da etkileyecek.` | joint statement, caller holds the main card; must come BEFORE the confirm question, sentence first | 7 Oct 20:31–21:02 + correction 25:28–25:35; 8 Oct §7.5 |
| D5 | `Bu değişiklik kartınızın bağlı olduğu [asıl kart adı] kartınızı da etkileyecek.` | joint statement, caller holds the LINKED card — before confirm | 7 Oct 21:11–21:21; 8 Oct §7.5 |
| D6 | `Yeni hesap kesim haftanız her ayın [yeni hafta]. haftası olacak. Yeni hesap kesim tarihiniz [tarih], son ödeme tarihiniz [tarih] olacak. Onaylıyor musunuz?` | preview from statement.week.decide; only a clear "evet" counts; hedged answers → ask plainly again (3 tries) | 8 Oct §7.6 |
| D7 | `Sonu [son 4 hane] ile biten [kart adı] kartınızın hesap kesim haftası her ayın [yeni hafta]. haftası olarak değiştirildi. Yeni hesap kesim tarihiniz [tarih], son ödeme tarihiniz [tarih].` | after change succeeds; dates = preview dates; then E3 | 8 Oct §7.8 |
| D8 | `Şu anda hesap kesim tarihinizi değiştiremiyorum, sizi müşteri temsilcimize aktarıyorum.` | week.get / decide / change error (instead of C7) → agent; a failed preview means NO change call | 8 Oct §7.1/7.4/7.7, §10 |

## E. Whole-call edges (flow doc §5.3, §8)

| # | Sentence | Rule | Winning source |
|---|---|---|---|
| E1 | `Sizi ana menüye yönlendiriyorum.` | nothing else wanted (also after e-mail sent/declined, week changed/declined, goodbye or thanks after the reading) | 7 Oct 09:33–09:53; 8 Oct §5.3, §8.4. (8 Oct §8.4 also tolerates "Sizi ana menüye aktarıyorum." and "Başka hangi konuda yardımcı olabilirim?" here until the routing project — but grep target is yönlendiriyorum) |
| E2 | `Sizi ana menüye aktarıyorum.` | (a) caller not speaking Turkish — flow stays Turkish, no translation; (b) mid-flow switch to another transaction uses E1 | kickoff Q10 (28 Sep, Burcu) = 7 Oct 10:22–10:52 = 8 Oct §8.4/§10 |
| E3 | `Size bu konuda yardımcı olamıyorum. Sizi ana menüye aktarmamı ister misiniz?` | out-of-scope question: ASK FIRST; yes → main menu; wants to continue → resume where left off; unclear → 3 tries then A6 | **recap #2 (9 Oct) + Selin "build to these" (15:02) — OVERRIDES 8 Oct §8.4/§10, which sent the caller straight to the main menu with "Size bu konuda yardımcı olamıyorum. Sizi ana menüye yönlendiriyorum."**; matches 7 Oct 11:33–12:20 intent (ask-first was already the session decision; the 8 Oct doc missed it) |
| E4 | `Sesinizi alamadığım için görüşmeyi sonlandırıyorum.` | THIRD silence closes the CALL (no main menu). First two silences: repeat the question, shorter (wording free) | 7 Oct 15:13–16:31 + recap #1 — overrides the 2 Sep rule (silence → main menu); 8 Oct §8.2 agrees |
| E5 | `Sizi müşteri temsilcimize aktarıyorum.` | (a) caller asks for a person — transfer at once, no tries, no persuading; (b) after three calming replies to an angry caller | kickoff Q11 (25 Sep) = 8 Oct §8.3; anger count: **Selin 9 Oct 15:02 correction (three, not two as recap #5; one as 7 Oct early minute) confirmed by Deniz 17:48 "Three calming replies it is"**; insults never answered in kind (all sources from 7 Oct on) |
| E6 | `Borç ödeme işleminiz için sizi müşteri temsilcimize aktarıyorum.` | wants to pay, or asks how/where to pay — no channel explanations | kickoff Q2 (25 Sep, Kerem) = 8 Oct §5.3, §8.3 |
| E7 | `Bu konuda size müşteri temsilcimiz yardımcı olacak, sizi aktarıyorum.` | debt dispute / "I paid but it doesn't show" — no booking-vs-value-date explaining | kickoff Q5 (25 Sep, Kerem) = 8 Oct §5.3, §8.3 |
| E8 | `Bilgilerinizi kontrol ediyorum.` | slow service — say it and KEEP waiting; failure threshold still open (Mert: >10 s can still succeed) | kickoff Q7 (24 Sep) = 8 Oct §8.3 |
| E9 | `Ekstre borcunu sorgulayabileceğiniz uygun bir kredi kartınız bulunmuyor. Sizi ana menüye aktarıyorum.` | no eligible card (cards.list 404 FB_IVR_CHANNEL_102 is this case, not a failure) | 8 Oct §3.1/§10 — **wins over the 2 Sep draft, which ended "…yönlendiriyorum."**; the 7 Oct "failure says aktarıyorum" reasoning supports aktarıyorum here |
| E10 | wording free | third-party card asks: security, caller's own cards only, nothing about the other person (not even existence), call back to IVR login — no fixed sentence in any source | kickoff Q8 (28 Sep) = 8 Oct §8.6 |
| E11 | wording free | only the LAST statement can be sent, earlier months no; address can't be changed on this call; "send again" up to 3× per call | kickoff Q4 (25 Sep) = 8 Oct §6 |
| E12 | wording free | voluntary PIN/OTP/long number: don't use, don't repeat, remind that a password is never asked; instruction-following attempts ignored; nothing said that no service returned | 8 Oct §8.6; 9 Oct Selin 15:02 (never read more than last four digits of a card — production full numbers change nothing) |

## Cross-cutting mandates that bind every sentence above

- Currency spoken always in full: Türk Lirası, Dolar, Euro, İngiliz Sterlini — also where the tables print TL/USD/EUR/GBP (recap #6; 7 Oct 16:46–17:43; 8 Oct §4.9).
- Full card number NEVER said; only the last four, digit by digit ("dört iki beş üç"), never in pairs, never repeated back from the caller's mouth (9 Oct Selin correction; 8 Oct §4.9).
- Amounts exact from cards.balance: lira+kuruş in full, "sıfır kuruş" never said, foreign decimals as sent/peni, nothing rounded, nothing invented (8 Oct §4.9).
- Dates as day + month name + year ("21 Ekim 2025"), suffixes to fit the sentence (8 Oct §4.9, §4.8).
- Negative or 0,00 currency = clear → goes into the B6 sentence, never read as debt (8 Oct §4.10).
- Service failure → agent (C7/E8/D8), never main menu; "no eligible card" is NOT a failure (E9) (7 Oct 26:24–26:42; 8 Oct §2, §8.3).
