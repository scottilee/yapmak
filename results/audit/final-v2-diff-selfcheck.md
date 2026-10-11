# Final v2 workflow diff

Generated 2026-10-11T18:18:28.876410+00:00. Static review only; no calls or simulations.

- Baseline: `results/final-v1/final.workflow.json`; SHA256 `f8e7d09c5bba59b8c684b57747b270dcad1ab6343b65b35f14971eb91035c629`.
- Repaired input: `results/final-v1/final.workflow.json`; SHA256 `f8e7d09c5bba59b8c684b57747b270dcad1ab6343b65b35f14971eb91035c629`.
- A generated report is not a passing verdict. Template matches, runtime bodies, routing and speech require the review noted below.

## Nodes and routing

Added nodes: none.
Removed nodes: none.
Entry point: `start` → `start`.


## Global handling and authored behavior


## API URLs and request bodies against contract

Reference: `hidden/final/sources/documents/2026-10-01-service-contract.md`. Compare both the parameter schema and preprocessing code: preprocessing can replace the actual body.

- **load_balance/load_balance**: URL/body/preprocessor unchanged; REVIEW: call.ani not declared (mock ignores it).
- **load_cards/load_cards**: URL/body/preprocessor unchanged; REVIEW: call.ani not declared (mock ignores it).
- **load_contact/load_contact**: URL/body/preprocessor unchanged; REVIEW: call.ani not declared (mock ignores it).
- **load_week/load_week**: URL/body/preprocessor unchanged; REVIEW: call.ani not declared (mock ignores it).
- **send_pdf/send_pdf**: URL/body/preprocessor unchanged; REVIEW: call.ani not declared (mock ignores it).
- **week_change_call/week_change_call**: URL/body/preprocessor unchanged; REVIEW: call.ani not declared (mock ignores it).
- **week_preview/week_preview**: URL/body/preprocessor unchanged; REVIEW: call.ani not declared (mock ignores it).

Schema checks do not prove runtime substitution or response success handling. Review original cardNumber preservation, current statementDay on both week requests, registered email, issued statementDate, numeric week/day, HTTP status and service result codes. No preprocessing code is executed by this checker.

## Dictated-sentence retention

Exact literal presence is checked in decoded workflow strings. NOT LITERAL is a review flag, not proof of omission: dynamic templates and Python concatenation must be inspected. Presence in notes/code also does not prove the sentence is reachable or spoken at the right point. Every required checklist row is listed.

| ID | v1 | v2 | Required wording |
|---|---|---|---|
| A1 | NOT LITERAL | NOT LITERAL | Hangi kartınızın borcunu öğrenmek istersiniz? Örneğin, [kart adı] veya [kart adı] diyebilirsiniz. |
| A2 | NOT LITERAL | NOT LITERAL | [kart adı] isimli birden fazla kartınız var. Kartınızın son dört hanesini söyler misiniz? |
| A3 | NOT LITERAL | NOT LITERAL | Son dört hanesi [4253] olan birden fazla kartınız var. Kartınızın son altı hanesini söyler misiniz? |
| A4 | literal | literal | Son altı hanesi aynı olan birden fazla kartınız var. Kart numaranızı söyler misiniz? |
| A5 | NOT LITERAL | NOT LITERAL | Sonu [4253] ile biten kartınıza ait … |
| A6 | literal | literal | Size şu anda yardımcı olamıyorum. Sizi ana menüye aktarıyorum. |
| B1 | NOT LITERAL | NOT LITERAL | Sonu [son 4 hane] ile biten [kart adı] kartınıza ait [tarih] tarihinde kesilen ekstre Türk Lirası borcunuz … |
| B2 | NOT LITERAL | NOT LITERAL | Türk Lirası borcunuz XXX TL, ödenmesi gereken minimum tutar ZZZ TL'dir. |
| B3 | NOT LITERAL | NOT LITERAL | Türk Lirası borcunuz XXX TL, kalan toplam borcunuz YYY TL'dir. Minimum ödemenizi yaptığınız için teşekkür ederiz. |
| B4 | NOT LITERAL | NOT LITERAL | Türk Lirası borcunuz XXX TL, ödenmesi gereken minimum tutar ZZZ TL, kalan toplam borcunuz YYY TL, kalan minimum ödeme tutarınız TTT TL'dir. |
| B5 | NOT LITERAL | NOT LITERAL | [Dolar] borcunuz XXX USD, kalan toplam borcunuz YYY USD, ödenmesi gereken minimum tutar ZZZ USD'dir. |
| B6.1 | NOT LITERAL | NOT LITERAL | [Türk Lirası] borcunuz bulunmamaktadır. |
| B6.2 | NOT LITERAL | NOT LITERAL | X ve Y borcunuz bulunmamaktadır. |
| B6.3 | NOT LITERAL | NOT LITERAL | X, Y ve Z borcunuz bulunmamaktadır. |
| B7 | NOT LITERAL | NOT LITERAL | Sonu [son 4 hane] ile biten [kart adı] kartınızın [hesap kesim tarihi] tarihli ekstresinden borcunuz bulunmamaktadır. Gelecek dönemler dahil toplam borcunuz GGG TL'dir. Son ödeme tarihiniz [son ödeme tarihi] olacaktır. |
| B8 | literal | literal | Başka bir kartınızın borcunu öğrenmek ister misiniz? |
| B9 | NOT LITERAL | NOT LITERAL | Borçlarınız için son ödeme tarihiniz [son ödeme tarihi]'dir. |
| B10 | literal | literal | Borçlarınız için son ödeme tarihiniz bugündür. |
| B11 | literal | literal | Hesap kesim tarihiniz bugün, ekstreniz saat 00.00 itibarıyla kesilecek. |
| C1 | literal | literal | Hesap kesim tarihinizi değiştirebilirim ya da ekstrenizi kayıtlı mail adresinize gönderebilirim. |
| C2 | literal | literal | Hesap kesim tarihinizi değiştirebilirim. |
| C3 | literal | literal | Ekstrenizi kayıtlı mail adresinize gönderebilirim. |
| C4 | literal | literal | Bankamızda kayıtlı bir e-posta adresiniz bulunmadığı için ekstrenizi gönderemiyorum. |
| C5 | NOT LITERAL | NOT LITERAL | Ekstrenizi [adres] adresine göndermemi ister misiniz? |
| C6 | literal | literal | Ekstreniz kayıtlı e-posta adresinize gönderildi. |
| C7 | literal | literal | Şu anda işleminizi gerçekleştiremiyorum, sizi müşteri temsilcimize aktarıyorum. |
| D1 | literal | literal | Hesap kesim tarihinizi yılda bir kez değiştirebilirsiniz. |
| D2 | NOT LITERAL | NOT LITERAL | [kart adı] kartınızın hesap kesim tarihi her ayın [hafta]. haftası olarak tanımlı. Bir sonraki hesap kesim tarihiniz [tarih], son ödeme tarihiniz [tarih]. Hesap kesim tarihinizi değiştirmek ister misiniz? |
| D3 | NOT LITERAL | NOT LITERAL | Hesap kesim tarihinizi ayın 1., 3. ya da 4. haftasına alabilirim. Hangisini tercih edersiniz? |
| D4 | NOT LITERAL | NOT LITERAL | Bu değişiklik kartınıza bağlı [bağlı kart adı] kartınızı da etkileyecek. |
| D5 | NOT LITERAL | NOT LITERAL | Bu değişiklik kartınızın bağlı olduğu [asıl kart adı] kartınızı da etkileyecek. |
| D6 | NOT LITERAL | NOT LITERAL | Yeni hesap kesim haftanız her ayın [yeni hafta]. haftası olacak. Yeni hesap kesim tarihiniz [tarih], son ödeme tarihiniz [tarih] olacak. Onaylıyor musunuz? |
| D7 | NOT LITERAL | NOT LITERAL | Sonu [son 4 hane] ile biten [kart adı] kartınızın hesap kesim haftası her ayın [yeni hafta]. haftası olarak değiştirildi. Yeni hesap kesim tarihiniz [tarih], son ödeme tarihiniz [tarih]. |
| D8 | literal | literal | Şu anda hesap kesim tarihinizi değiştiremiyorum, sizi müşteri temsilcimize aktarıyorum. |
| E1 | literal | literal | Sizi ana menüye yönlendiriyorum. |
| E2 | literal | literal | Sizi ana menüye aktarıyorum. |
| E3 | literal | literal | Size bu konuda yardımcı olamıyorum. Sizi ana menüye aktarmamı ister misiniz? |
| E4 | literal | literal | Sesinizi alamadığım için görüşmeyi sonlandırıyorum. |
| E5 | literal | literal | Sizi müşteri temsilcimize aktarıyorum. |
| E6 | literal | literal | Borç ödeme işleminiz için sizi müşteri temsilcimize aktarıyorum. |
| E7 | literal | literal | Bu konuda size müşteri temsilcimiz yardımcı olacak, sizi aktarıyorum. |
| E8 | NOT LITERAL | NOT LITERAL | Bilgilerinizi kontrol ediyorum. |
| E9 | literal | literal | Ekstre borcunu sorgulayabileceğiniz uygun bir kredi kartınız bulunmuyor. Sizi ana menüye aktarıyorum. |
| E10 | behavioral review | behavioral review | wording free |
| E11 | behavioral review | behavioral review | wording free |
| E12 | behavioral review | behavioral review | wording free |

## Test-customer data scan

Exact-value checks cover customer numbers, full/masked card numbers and email addresses, plus complete customer records. Product names, last-four digits and numeric amounts may coincide with document examples; they are not automatically proof of leakage. Code and prompt differences above still need a human check for customer-specific branches.

Exact identifier hits: **0**.
Complete serialized customer-record matches: 0.

## Operator sign-off

- [ ] Repair owner confirmed this is the completed export, not an intermediate file.
- [ ] Every changed routing/global rule agrees with the latest email decisions.
- [ ] Every NOT LITERAL sentence was located in an assembled template or recorded as a defect.
- [ ] Changed API preprocessing preserves the contract; success checks are correct.
- [ ] No fixture-specific answers or branches were introduced.
- [ ] Required live checks pass; static comparison is not a substitute.
