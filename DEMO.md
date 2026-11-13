# FieldSafe project demo

## Start the demo

Install the project requirements once, then seed the separate demo database and launch the app:

```powershell
python -m pip install -r requirements.txt
python scripts/seed_demo.py
$env:DATABASE = "instance/demo.db"
python app.py
```

Open `http://127.0.0.1:5000`. The demo seeder is repeatable; stable idempotency keys prevent duplicate sample reports. It writes only to `instance/demo.db`, leaving the default development database separate.

## Suggested 5 minute walkthrough

1. **New report:** submit a new critical observation using `INSAB1234`, `V01-CRITICAL`, PIN `560001`, and an Emergency urgency. Show the resulting report ID, category, P1 priority, and assignment.
2. **User dashboard:** find the new report by ID; show report counts, category, status, zone, and handler.
3. **Handler desk:** inspect the seeded roster and cases; move an Assigned report to In Progress and then Resolved. Its open handler load should drop.
4. **Routing management:** compare all six PIN zones, primary and deputy loads, current queue, and fallback/override policy.
5. **Analytics:** show the category and zone distributions, assignment outcomes, and resolved/unresolved totals.
6. **Edge cases:** inspect the seeded malformed-ID report (rejected before dispatch) and the valid report with PIN `900001` (central correction queue).

## Demo data included

The eight synthetic reports cover Critical, Major, Minor, Advisory, Passed, a critical emergency override, an unknown routing zone, and a malformed inspector ID. They use fictitious names and `example.gov` addresses. No production or personal report data is included.

To reset the walkthrough state, stop the local server and remove only `instance/demo.db`, then run the seeder again. This database contains demo-only data.
