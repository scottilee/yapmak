// Paths, error catalogue and the OpenAPI document the builder reads. Everything here mirrors the bank's service contract
// (sources/documents/2026-10-01-service-contract.md): POST https://<base>/voice/v1/<service>, request {data, call},
// response {data, result}; the test-environment answers themselves come from customers.json.
export const ROUTES = {
  "POST /voice/v1/cards.list": "cards.list",
  "POST /voice/v1/cards.balance": "cards.balance",
  "POST /voice/v1/statement.week.get": "statement.week.get",
  "POST /voice/v1/statement.week.decide": "statement.week.decide",
  "POST /voice/v1/statement.week.change": "statement.week.change",
  "POST /voice/v1/contact.email.get": "contact.email.get",
  "POST /voice/v1/statement.pdf.send": "statement.pdf.send",
};

// Contract section 4 / 6: the error each service returns when the customer, card or week is not in the test data.
export const NOT_FOUND = {
  "cards.list": [404, "FB_IVR_CHANNEL_102", "WARNING", "Müşteriye ait geçerli kart bilgisi bulunamadı."],
  "cards.balance": [404, "FB_IVR_CHANNEL_120", "WARNING", "Kart bakiye servisi hatası: kart bulunamadı"],
  "statement.week.get": [404, "FB_IVR_CHANNEL_121", "WARNING", "Hesap kesim haftası servisi hatası: kart bulunamadı"],
  "statement.pdf.send": [404, "FB_IVR_CHANNEL_107", "WARNING", "Pdf dokümanı bulunamadı"],
  "statement.week.decide": [400, "INVALID_ARGUMENTS_ERROR", "ERROR", "card number or statement week not valid"],
  "statement.week.change": [400, "INVALID_ARGUMENTS_ERROR", "ERROR", "card number or statement week not valid"],
  "contact.email.get": [400, "INVALID_ARGUMENTS_ERROR", "ERROR", "customer number not valid"],
};

// Fields the look-up needs (contract section 5); a missing or empty one is a 400 INVALID_ARGUMENTS_ERROR ("<field> cannot be empty").
export const REQUIRED = {
  "cards.list": ["customerNo"],
  "cards.balance": ["cardNumber"],
  "statement.week.get": ["cardNumber"],
  "statement.week.decide": ["cardNumber", "newStatementWeek"],
  "statement.week.change": ["cardNumber", "newStatementWeek"],
  "contact.email.get": ["customerNo"],
  "statement.pdf.send": ["customerNo"],
};

export function openapi(origin) {
  const str = (d, extra = {}) => ({ type: "string", description: d, ...extra });
  const num = d => ({ type: "number", description: d });
  const int = d => ({ type: "integer", description: d });
  const bool = d => ({ type: "boolean", description: d });
  const dmy = d => str(d + ", format dd.MM.yyyy (e.g. 05.11.2026)");
  const result = { type: "object", description: "Result envelope, present on every answer. Success = HTTP 200 and returnCode '1'.", properties: {
    guid: str("Trace id"), returnCode: str("'1' on success; otherwise an error code (INVALID_ARGUMENTS_ERROR, FB_IVR_CHANNEL_1xx, FBE00099)"),
    messageText: str("Log message, not for the caller"), code: str("Same as returnCode"), message: str("Same as messageText"),
    type: str("null on success, 'ERROR' or 'WARNING' on failure"),
    details: { type: "object", properties: { guid: str("Trace id"), rootCause: str("Diagnostic"), errorOrigin: str("Diagnostic") } } } };
  const errorResponse = (desc) => ({ description: desc, content: { "application/json": { schema: { type: "object", description: "Error answer: no data object, only result", properties: { result } } } } });
  const debt = cur => ({ type: "object", description: `Debt block for ${cur}. The block can be MISSING for a card without this currency; a missing block is not NO_DEBT.`, properties: {
    statementPaymentStatus: str("HAS_DEBT or NO_DEBT for the statement debt in this currency"), transferAmount: num("Amount carried over from the previous period"),
    statementDebt: num("Statement debt"), minPayment: num("Minimum payment on the statement"), remainingDebt: num("What is left of the statement debt after payments since the statement; 0 when fully paid"),
    remainingMinPayment: num("What is left of the minimum payment after payments since the statement; 0 when the minimum was paid"), currentPeriodExpense: num("Spending after the statement"),
    totalDebt: num("Total debt including spending after the statement; negative = credit balance"), totalDebtPaymentStatus: str("HAS_DEBT or NO_DEBT for the total debt"),
    remainAutomaticPaymentAmount: num("Remaining automatic payment amount; only meaningful when automaticPaymentFlag is Y") } });
  const call = { type: "object", description: "Call metadata the bank logs; not checked in the test environment", properties: { ani: str("Caller's phone number"), lang: str("Caller language code, e.g. tr") } };
  const op = (summary, description, props, required, dataProps, dataDesc, errors) => ({ post: { summary, description,
    requestBody: { required: true, content: { "application/json": { schema: { type: "object", description: "Contract envelope: service fields under data, call metadata under call",
      properties: { data: { type: "object", description: "Service request fields", properties: props, required }, call }, required: ["data"] } } } },
    responses: { "200": { description: "success (result.returnCode '1')", content: { "application/json": { schema: { type: "object", properties: { data: { type: "object", description: dataDesc, properties: dataProps }, result } } } } }, ...errors } } });
  const E400 = { "400": errorResponse("INVALID_ARGUMENTS_ERROR: a required field is missing or empty (result.type ERROR)") };
  const E500 = { "500": errorResponse("FBE00099: technical error on the bank's side (result.type ERROR)") };
  const custNo = str("Customer number the phone menu passes with the call; string or number both accepted");
  const cardNo = str("cardNumber exactly as cards.list returned it (masked in the test environment, e.g. 540000******1234); never rebuilt from digits the caller says");
  const week = int("Requested statement week of the month, 1-4 (number or string); must differ from the card's current statementWeek");
  const day = int("The card's current statementDay from statement.week.get");
  const paths = {
    "/voice/v1/cards.list": op("Cards of the customer the assistant may talk about", "Only active cards (status A) come back. Two cards can share productName and cardNumberLast4. productName is free text and may be empty.",
      { customerNo: custNo, aiFlow: str("Use case asking; 'CardOps' for this flow", { default: "CardOps" }) }, ["customerNo", "aiFlow"], {
      cards: { type: "array", description: "The customer's eligible credit cards", items: { type: "object", properties: {
        cardNumber: str("Masked card number (first six and last four visible); send this value unchanged to the card-level services"), cardNumberLast4: str("Last four digits (not unique)"),
        productName: str("Card product name as the card system returns it; may be an empty string"), status: str("Card status; 'A' active"), isMainCard: bool("false for a card that is not the customer's own main card (supplementary); it is still listed") } } },
      validCardsCount: int("Number of cards returned"), exitState: str("'1_CARD' or 'MULTI_CARD'") }, "Card list",
      { "404": errorResponse("FB_IVR_CHANNEL_102 (result.type WARNING): the customer has no valid card the assistant can work with. Not a service failure."), ...E500 }),
    "/voice/v1/cards.balance": op("Statement and due dates and the debt per currency of one card", "Debt blocks debtTL, debtUSD, debtEUR, debtGBP; any block can be missing.",
      { cardNumber: cardNo }, ["cardNumber"], {
      cardNumber: str("Masked differently from cards.list (first 4 + last 4); do not use it for matching"), cardNumberLast4: str("Last four digits"), productName: str("Card product name"),
      statementDate: dmy("Date of the last issued statement"), lastPayDate: dmy("Due date of the last issued statement"), nextStatementDate: dmy("Coming statement date"), nextLastPayDate: dmy("Coming due date"),
      debtTL: debt("Türk Lirası (TL)"), debtUSD: debt("Dolar (USD)"), debtEUR: debt("Euro (EUR)"), debtGBP: debt("İngiliz Sterlini (GBP)"),
      statementPaymentStatus: str("HAS_DEBT or NO_DEBT for the card overall (statement debt)"), totalDebtPaymentStatus: str("HAS_DEBT or NO_DEBT for the card overall (total debt)"),
      automaticPaymentFlag: str("'Y' when an automatic payment instruction exists, else 'N'") }, "Balance",
      { ...E400, "404": errorResponse("FB_IVR_CHANNEL_120 (WARNING): card not found"), ...E500 }),
    "/voice/v1/statement.week.get": op("Current statement week and day of a card, joint statement info", "relationType is '' for a card with its own statement, 'M' when this is the main card of a pair sharing one statement, 'C' when this card is linked to a main card. Changing the week on either card moves both.",
      { cardNumber: cardNo }, ["cardNumber"], {
      cardNumber: str("Masked card number"), cardNumberLast4: str("Last four digits"), productName: str("Card product name"),
      statementWeek: int("Current statement week of the month, 1-4"), statementDay: int("Current statement day of the month"),
      statementDate: dmy("Last statement date"), lastPayDate: dmy("Last due date"), nextStatementDate: dmy("Next statement date"), nextLastPayDate: dmy("Next due date"),
      relationType: str("'' (own statement), 'M' (main card of a shared statement) or 'C' (card linked to a main card)"),
      relatedCardNumber: str("Masked number of the other card of the pair; '' otherwise"), relatedCardProductName: str("Product name of the other card of the pair; '' otherwise") }, "Statement week",
      { "404": errorResponse("FB_IVR_CHANNEL_121 (WARNING): card not found"), ...E500 }),
    "/voice/v1/statement.week.decide": op("Preview the dates the card would get with the requested week; changes nothing", "Do not call it for the week the card already has (error). Call before statement.week.change and read the preview dates to the caller.",
      { cardNumber: cardNo, newStatementWeek: week, statementDay: day }, ["cardNumber", "newStatementWeek", "statementDay"], {
      statementDate: dmy("First statement date under the requested week"), statementDueDate: dmy("First due date under the requested week (named statementDueDate here, not lastPayDate)"),
      statementDay: int("Statement day under the requested week"), responseCode: int("0 = fine"), responseMessage: str("'Success'") }, "Preview",
      { ...E400, ...E500 }),
    "/voice/v1/statement.week.change": op("Change the card's statement week (side effect)", "Call only after the caller agreed to the dates from statement.week.decide. The dates to tell the caller are the preview's; ignore statementDay here.",
      { cardNumber: cardNo, newStatementWeek: week, statementDay: day }, ["cardNumber", "newStatementWeek", "statementDay"], {
      responseCode: int("0 on success"), responseMessage: str("'00' on success"), statementWeek: str("New week, as a STRING"), statementDay: str("Recalculated day, as a STRING; ignore"),
      exitState: str("'OK' on success") }, "Change result",
      { ...E400, "401": errorResponse("gateway: token missing or expired"), ...E500 }),
    "/voice/v1/contact.email.get": op("Registered e-mail / phone of the customer", "The registered e-mail is ibanEmail (ttsEmail is the same address prepared for reading aloud). No registered e-mail = communicationType 'Phone' and/or empty ibanEmail; check the field. The iban prefix is historical.",
      { customerNo: custNo, intAddressInfoType: str("'E' e-mail, 'P' phone, 'B' both", { enum: ["E", "P", "B"], default: "E" }) }, ["customerNo", "intAddressInfoType"], {
      communicationType: str("'Both', 'Phone' or 'Email'"), ibanCountryCode: str("Phone country code"), ibanAreaCode: str("Phone area code"), ibanPhoneNum: str("Phone number"),
      ibanEmail: str("Registered e-mail address; '' when none"), ttsEmail: str("Same address prepared for speech; '' when none"), commGramType: str("Internal"), exitState: str("'Done'") }, "Contact",
      { ...E400, ...E500 }),
    "/voice/v1/statement.pdf.send": op("E-mail the statement PDF (side effect)", "Sends the PDF of the statement dated statementDate to emailAddress. The backend does not check the address against the registered one; the assistant must only use the registered address.",
      { customerNo: custNo, cardNumber: cardNo, currencyType: str("'TL', 'USD', 'EUR' or 'GBP'", { enum: ["TL", "USD", "EUR", "GBP"], default: "TL" }),
        statementDate: dmy("The statementDate from cards.balance (the issued statement)"), emailAddress: str("The registered e-mail address (ibanEmail from contact.email.get)") },
      ["customerNo", "cardNumber", "currencyType", "statementDate", "emailAddress"], { exitState: str("'DONE' when the statement was sent") }, "Send result",
      { ...E400, "404": errorResponse("FB_IVR_CHANNEL_107 (WARNING): no statement document to send"), ...E500 }),
  };
  for (const [p, v] of Object.entries(paths)) v.post.operationId = p.split("/").pop().replace(/\./g, "_");   // cards_list, statement_week_get, ...
  return { openapi: "3.0.3",
    info: { title: "Freya Bank voice services: statement and debt (test environment mock)", version: "1.0.0",
      description: "Seven POST services under /voice/v1/. Request {data, call}; response {data, result}; success = HTTP 200 and result.returnCode '1'. Error answers carry result only. Dates dd.MM.yyyy strings, amounts JSON numbers. The test environment does not check tokens, headers, call or aiFlow." },
    servers: [{ url: origin }], paths };
}
