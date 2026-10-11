// Freya Bank mock for the final case: the seven statement/debt services of the 2026-10-01 service contract, answered exactly as
// the bank's test environment does (customers.json = test-environment/test-customers.json: per customer, per service, per masked
// card number, per requested week: http status, response body, optional delaySeconds). Nothing is made up: a customer, card or
// week that is not in the file gets the contract's error for that service.
import data from "./customers.json";
import { ROUTES, NOT_FOUND, REQUIRED, openapi } from "./contract.js";

const CUSTOMERS = new Map((data.customers || []).map(c => [String(c.customerNo), c]));
const state = { calls: [] };
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "*" };
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", ...CORS } });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const guid = () => crypto.randomUUID().replace(/-/g, "");

function errorBody(code, type, text) {
  const g = guid();
  const rootCause = code === "INVALID_ARGUMENTS_ERROR" ? "com.freyabank.ivrgateway.ivrchannel.rest.exception.InvalidArgumentsException"
                  : code === "FBE00099" ? "TechnicalError" : "com.freyabank.ivrgateway.ivrchannel.rest.exception.NotFoundException";
  return { result: { guid: g, returnCode: code, messageText: text, code, message: text, type, details: { guid: g, rootCause, errorOrigin: "ivr-gateway-test:ivr-channel-v0" } } };
}
const notFound = service => { const [http, code, type, text] = NOT_FOUND[service]; return [http, errorBody(code, type, text)]; };
const invalid = text => [400, errorBody("INVALID_ARGUMENTS_ERROR", "ERROR", text)];
const empty = v => v === undefined || v === null || String(v).trim() === "";
const NAMES = { customerNo: "customer number", cardNumber: "card number", newStatementWeek: "statement week" };

function lookup(service, q) {
  for (const f of REQUIRED[service] || []) if (empty(q[f])) return invalid(`${NAMES[f] || f} cannot be empty`);
  if (service === "contact.email.get" && "intAddressInfoType" in q && empty(q.intAddressInfoType)) return invalid("intAddressInfoType cannot be empty");
  const cardKeyed = !["cards.list", "contact.email.get", "statement.pdf.send"].includes(service);
  let c;
  if (cardKeyed) {                                            // the card decides; the customer number is not part of these requests
    const key = String(q.cardNumber).trim();
    for (const cand of CUSTOMERS.values()) {
      const entry = (cand.services || {})[service];
      if (entry && key in entry) { c = cand; break; }
    }
    if (!c && !empty(q.customerNo)) c = CUSTOMERS.get(String(q.customerNo).trim());   // tolerate a differently masked number from a known customer
    if (!c) return notFound(service);
  } else {
    c = CUSTOMERS.get(String(q.customerNo).trim());
    if (!c) return notFound(service);
  }
  let entry = (c.services || {})[service];
  if (!entry) return notFound(service);
  if (!("http" in entry)) {                                   // keyed by masked card number
    const key = String(q.cardNumber).trim();
    entry = entry[key] ?? (key.length >= 4 ? Object.entries(entry).filter(([k]) => k.slice(-4) === key.slice(-4)) : []);
    if (Array.isArray(entry)) entry = entry.length === 1 ? entry[0][1] : undefined;
    if (!entry) return notFound(service);
    if (!("http" in entry)) {                                 // keyed by requested week
      const wk = String(q.newStatementWeek).trim().replace(/\.0$/, "");
      entry = entry[wk];
      if (!entry) return notFound(service);
    }
  }
  return [entry.http ?? 200, entry.response ?? entry.yanit ?? {}, entry.delaySeconds ?? entry.gecikmeSaniye ?? 0];
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (path === "/health") return json({ status: "ok", ok: true, ts: new Date().toISOString(), customers: CUSTOMERS.size, services: Object.values(ROUTES) });
    if (path === "/openapi.json") return json(openapi(url.origin));
    if (path === "/records") return json({ calls: state.calls.slice(-200) });
    if (path === "/oauth2/token") return json({ access_token: "test-" + guid(), token_type: "Bearer", expires_in: 1800 });
    const service = ROUTES[request.method + " " + path] || ROUTES["POST " + path];
    if (!service) return json({ error: "not found", path, paths: Object.keys(ROUTES) }, 404);
    let q = {};
    if (request.method === "GET") { for (const [k, v] of url.searchParams) q[k] = v; }
    else { try { q = await request.json(); } catch { return json(errorBody("INVALID_ARGUMENTS_ERROR", "ERROR", "request body is not valid JSON"), 400); } }
    if (!q || typeof q !== "object") q = {};
    if (q.data && typeof q.data === "object") q = { ...q.data, call: q.call };   // contract envelope {data, call}
    // the panel's "Test API Request" sends unfilled template variables: answer with the first customer's record (as the organisers' example does)
    const isTpl = v => typeof v === "string" && (v.startsWith("{{") || v.startsWith("%7B%7B"));
    const first = data.customers[0];
    if (isTpl(q.customerNo) || (isTpl(q.cardNumber) && empty(q.customerNo))) q.customerNo = first.customerNo;
    if (isTpl(q.cardNumber)) q.cardNumber = (first.services["cards.list"].response.data.cards[0] || {}).cardNumber;
    if (isTpl(q.newStatementWeek)) q.newStatementWeek = "2";
    if (isTpl(q.statementDay)) q.statementDay = 5;
    const [status, body, delay] = lookup(service, q);
    state.calls.push({ t: new Date().toISOString(), service, customerNo: q.customerNo, cardNumber: q.cardNumber, week: q.newStatementWeek, status });
    if (delay) await sleep(Math.min(delay, 25) * 1000);
    return json(body, status);
  },
};
