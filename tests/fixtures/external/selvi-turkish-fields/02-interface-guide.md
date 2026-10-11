# Selvi interface guide

This guide explains the bank's Turkish transport names in English. These definitions are authoritative, not naming hints or optional aliases. Property order carries NO semantic meaning. All seven operations are POST with JSON request/response bodies on their same-named English paths. Calls remain English. Never translate an enum value or infer a value from its array position.

## 1. Request arguments
All arguments listed are required except add_note.metin and close_call.neden. The latter must be present for every outcome except soz_verildi, for which it must be omitted. No required argument is intentionally missing from the schema.

| Operation | Turkish property | Meaning |
|---|---|---|
| verify_identity | `musteri_no` | `musteri_no` is the customer reference from call variable customer_id, never the product identifier. |
| verify_identity | `soru` | `soru` is the identifier of the security question being answered. |
| verify_identity | `cevap` | `cevap` is the complete normalized answer to that security question. |
| get_account | `musteri_no` | `musteri_no` is the customer reference from call variable customer_id, never the product identifier. |
| create_promise | `musteri_no` | `musteri_no` is the customer reference from call variable customer_id, never the product identifier. |
| create_promise | `sozlesme` | `sozlesme` is the product identifier returned for the relevant product. |
| create_promise | `tutar` | `tutar` is the promised amount, as a JSON number. |
| create_promise | `tarih` | `tarih` is the promise date for create_promise or callback date for schedule_callback, as an ISO date string. |
| add_note | `musteri_no` | `musteri_no` is the customer reference from call variable customer_id, never the product identifier. |
| add_note | `sozlesme` | `sozlesme` is the product identifier returned for the relevant product. |
| add_note | `neden` | `neden` is the product note reason for add_note or closing reason for close_call. |
| add_note | `metin` | `metin` is optional free text attached to a product note. |
| schedule_callback | `musteri_no` | `musteri_no` is the customer reference from call variable customer_id, never the product identifier. |
| schedule_callback | `tarih` | `tarih` is the promise date for create_promise or callback date for schedule_callback, as an ISO date string. |
| schedule_callback | `saat` | `saat` is the local callback clock time as HH:MM. |
| transfer_to_agent | `musteri_no` | `musteri_no` is the customer reference from call variable customer_id, never the product identifier. |
| transfer_to_agent | `kuyruk` | `kuyruk` is the transfer destination queue. |
| close_call | `musteri_no` | `musteri_no` is the customer reference from call variable customer_id, never the product identifier. |
| close_call | `sonuc` | `sonuc` is the final call outcome. |
| close_call | `neden` | `neden` is the product note reason for add_note or closing reason for close_call. |

## 2. Response slots
All response properties are required. Products appear directly under urunler; its items use the product properties listed below. On failed get_account, basarili is false and urunler may be an empty array; the agent must not claim there are no debts from that failure. No response provides an error message, receipt identifier or format hint.

| Operation | Turkish property | Meaning |
|---|---|---|
| verify_identity | `basarili` | `basarili` is whether this operation completed successfully; HTTP 200 alone does not mean success. |
| verify_identity | `cevap_dogrulandi` | `cevap_dogrulandi` is whether this individual answer passed. |
| verify_identity | `tum_sorular_dogrulandi` | `tum_sorular_dogrulandi` is whether all three security questions have passed. |
| verify_identity | `kalan_deneme` | `kalan_deneme` is the number of wrong answers remaining across the whole identity check. |
| get_account | `basarili` | `basarili` is whether this operation completed successfully; HTTP 200 alone does not mean success. |
| get_account | `urunler` | `urunler` is the array containing the returned products. |
| get_account | `sozlesme` | `sozlesme` is the product identifier within a returned product, passed unchanged as sozlesme on product writes. |
| get_account | `tur` | `tur` is the product type within a returned product. |
| get_account | `geciken_tutar` | `geciken_tutar` is the full past-due amount within a returned product. |
| get_account | `gecikme_gunu` | `gecikme_gunu` is the integer number of days late within a returned product. |
| create_promise | `basarili` | `basarili` is whether this operation completed successfully; HTTP 200 alone does not mean success. |
| add_note | `basarili` | `basarili` is whether this operation completed successfully; HTTP 200 alone does not mean success. |
| schedule_callback | `basarili` | `basarili` is whether this operation completed successfully; HTTP 200 alone does not mean success. |
| transfer_to_agent | `basarili` | `basarili` is whether this operation completed successfully; HTTP 200 alone does not mean success. |
| close_call | `basarili` | `basarili` is whether this operation completed successfully; HTTP 200 alone does not mean success. |

## 3. Security and codes
soru has values dogum_yili (birth year), ilce (district), guvenlik_sayisi (six-digit security number). Their order is mandated by policy, not enum ordering. A wrong answer can be a successfully processed operation: basarili=true, cevap_dogrulandi=false, tum_sorular_dogrulandi=false. A fully correct final answer sets both verification flags true. An operation failure does not prove an identity answer wrong. kalan_deneme is authoritative; never infer it from the position of a boolean.
Product tur has values doner_hesap and tasit_borcu, with spoken names in policy section 3. neden, kuyruk and sonuc take only the policy's exact codes. All dates use the supplied call clock. Unsuccessful writes leave no new ledger entry; basarili=false must never be described as a successful action.
