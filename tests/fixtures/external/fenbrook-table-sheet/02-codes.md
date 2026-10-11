FCCU CODES LIST v1.0 — case-sensitive; omit reason EXACTLY where listed "none".

OUTCOMES (close_call.outcome)

  CCC-OK      : (no reason)
  CCC-NO      : F-no | F-wrong | F-unclear
  CCC-FAIL    : F-pin | F-dec
  CCC-TR      : F-person

QUEUES (transfer_to_agent.queue)

  fcc-desk

NOTES

  The add_note tool is not used by call sheet v1.0.
  schedule_callback is not used.
  transfer_to_agent only uses queue fcc-desk.

VOCABULARY IN THIS PACKAGE

  Field names from the OpenAPI (mapped by the builder, not spoken):
    cust_ref    -> customer identifier
    pi_code     -> the security answer field
    payment     -> the amount in create_promise
    amt_due     -> the full outstanding amount returned by get_account
    dl_days     -> the days-past returned by get_account
    minimum     -> the floor returned by get_account (one per product)