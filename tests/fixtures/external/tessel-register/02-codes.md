| Code group | Exact values and meanings |
|---|---|
| Authority | TS-C4, effective 10 October 2026; only the combinations below are valid. Digits are STRING codes, never JSON numbers. |
| Outcome 10 | Saved promise; omit reason. |
| Outcome 20 | R10 = refusal, declined hardship support or expired limit; R17 = dispute; R99 = failed save. |
| Outcome 30 | R30 = human transfer; R31 = hardship support transfer. |
| Outcome 40 | R40 = failed identity; R41 = declined identity. |
| Outcome 50 | R50 = unclear holder; R51 = scheduled callback; R52 = no callback; R53 = wrong number; R54 = deceased. |
| Transfer queues | Desk-4 for R30; Care-4 for R31. No other queues. |
| Notes endpoint | Retained transport reason enum R10, R17, R99; campaign never calls add_note. No active note reasons. |
| Paid route | Absent. No paid outcome, reason or note. |
