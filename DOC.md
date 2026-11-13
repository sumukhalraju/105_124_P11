# FieldSafe Food Safety Inspection Portal

FieldSafe is a Flask + SQLite production-style reference implementation of the photographed P11 Food Safety Inspection Portal brief. It accepts structured inspection reports, validates identifiers using both an explicit DFA and equivalent regular expressions, classifies reports into exactly five categories, routes valid reports through a six-zone dispatch table, and exposes operational dashboards.

## Requirements traceability

| Brief requirement | Implementation |
| --- | --- |
| Inspector ID `INS` + 2 letters + 4 digits | `portal/validation.py` explicit DFA and `^INS[A-Z]{2}\d{4}$` regex |
| Violation code `V` + 2 digits + category token | Explicit DFA and `^V\d{2}-[A-Z][A-Z0-9_]*$` regex |
| DFA/regex comparison | `validate_identifiers()` returns both outcomes and agreement |
| Five categories | Critical, Major, Minor, Advisory, Passed; unknown category tokens are rejected, never silently mapped |
| Deterministic conflicts | Critical > Major > Minor > Advisory > Passed |
| Six routing zones | Z1–Z6, keyed by the first digit of a six-digit PIN |
| Balanced handler capacity | Primary officer then deputy; maximum 10 open cases per handler |
| Fallback and escalation | Unknown zone → Central correction queue; unavailable/full handlers → queue; Critical/Emergency → cross-zone priority pool |
| Lifecycle | Pending → Assigned → In Progress → Resolved, with an auditable `status_history` table |
| Dashboards | Submission, user report dashboard with clickable report specifications and status history, handler desk, routing management, analytics; report exports to print/PDF, JSON, and CSV |
| Database integration | SQLite schema, indexes, seed handler roster, transactional report/dispatch persistence |
| Testing | Pytest unit/API/end-to-end coverage in `tests/` |

The prompt mentions MERN but also explicitly requires a Flask backend and SQLite integration. This implementation follows the explicit Flask/SQLite requirement and uses a dependency-light HTML/CSS/JavaScript frontend so it can run as one deployable service.

## Architecture

```text
Browser UI (static/index.html, app.js, styles.css)
        ↓ JSON REST
Flask application (app.py)
        ├── validation service (DFA + regex + classifier)
        ├── dispatch service (routing table + capacity allocator)
        └── SQLite (reports, dispatches, handlers, status_history)
```

The application factory is `create_app()`. It initializes the schema and seeds two handlers for each zone. A file-backed database is used by default at `instance/portal.db`; tests use a fresh temporary database. The dashboard navigation side panel can be expanded or collapsed with the header toggle, and the browser remembers that choice.

## Formal validation model

Inspector DFA states are `q0` start, `q1` after `I`, `q2` after `IN`, `q3` after `INS`, `q4`/`q5` after two uppercase letters, `q6`–`q9` after four digits; only `q9` accepts. The equivalent regex is:

```text
^INS[A-Z]{2}[0-9]{4}$
```

Violation DFA states are `q0` start, `q1` after `V`, `q2`/`q3` after two digits, `q4` after `-`, `q5` after the first uppercase category letter, and `q6` for additional uppercase letters, digits, or underscores. `q5` and `q6` accept. The equivalent regex is:

```text
^V[0-9]{2}-[A-Z][A-Z0-9_]*$
```

The API accepts a report only if DFA and regex results agree. A syntactically valid but unmapped token such as `V77-UNKNOWN` is stored as `Rejected` with an actionable validation message.

## Classification

Mapped tokens are `CRITICAL`, `MAJOR`, `MINOR`, `ADVISORY`, and `PASSED`. Description patterns are also evaluated. When multiple patterns match, the documented deterministic precedence is:

```text
Critical > Major > Minor > Advisory > Passed
```

Emergency urgency is promoted to priority 1 and activates the emergency dispatch pool. The category and the explanation are persisted with the original report.

## Routing and dispatch

| Zone | PIN prefix | Primary branch | Team | Depot |
| --- | --- | --- | --- | --- |
| Z1 North | 1 | North Regulatory Branch | Alpha | Delhi Depot |
| Z2 North Central | 2 | North Central Regulatory Branch | Bravo | Lucknow Depot |
| Z3 West | 3 | West Regulatory Branch | Charlie | Jaipur Depot |
| Z4 West Central | 4 | West Central Regulatory Branch | Delta | Mumbai Depot |
| Z5 South | 5 | South Regulatory Branch | Echo | Bengaluru Depot |
| Z6 East | 6 | East Regulatory Branch | Foxtrot | Kolkata Depot |

The allocator first prefers an available local district officer, then the local deputy. A handler is eligible only while its open load is below `min(capacity, 10)`. Critical or Emergency work prefers the local zone and can then use an available officer in another zone. If no handler is eligible, the report remains Pending and the dispatch decision is Queued. Valid reports with an unknown prefix (for example `900001`) go to the Central correction queue. Malformed PINs are rejected before dispatch.

Report creation runs under a SQLite `BEGIN IMMEDIATE` transaction. An optional `idempotency_key` is unique, and each report has at most one dispatch row, preventing duplicate assignments in normal concurrent submissions.

## REST API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service health |
| GET | `/api/validation/spec` | Identifier patterns, categories and priority order |
| POST | `/api/reports` | Validate, classify, persist and dispatch a report |
| GET | `/api/reports?search=&status=&handler_id=` | Search/filter reports |
| GET | `/api/reports/<id>` | Detail and status history |
| PATCH | `/api/reports/<id>/status` | Progress through the lifecycle |
| GET | `/api/handlers` | Roster with calculated open loads |
| PATCH | `/api/handlers/<id>` | Set availability/capacity, enforcing current load |
| GET | `/api/routing` | Six-zone routing table and fallback policy |
| GET | `/api/dashboard/stats` | Total, lifecycle and queue counts |
| GET | `/api/analytics` | Category, zone and assignment distributions |

Example request:

```json
{
  "reporter_name": "Priya Sharma",
  "reporter_email": "priya@example.gov",
  "inspector_id": "INSAB1234",
  "violation_code": "V01-CRITICAL",
  "pin_code": "560001",
  "description": "Critical contamination risk near raw meat storage.",
  "urgency": "High",
  "idempotency_key": "mobile-submission-001"
}
```

Successful valid submissions return `201` and include `id`, `validation_status`, `category`, `priority`, `status`, `assignment_status`, handler/routing fields, decision, and status history. Invalid structured input returns `400`; malformed identifiers are persisted as a rejected report so the original submission and validation reason remain auditable.

## Local setup

```powershell
py -m venv .venv
\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open `http://127.0.0.1:5000`. Set `PORT` to use another local port. The default database is created automatically. For a clean environment, remove only the generated `instance/portal.db` file and restart; it is ignored by Git.

## Verification

```powershell
py -m pytest -q
py -m pytest --cov=portal --cov=app --cov-report=term-missing
node --check static/app.js
```

The suite covers valid/invalid DFA and regex inputs, five categories, conflict precedence, unmapped codes, malformed payloads, all zones, fallback, handler availability/capacity, emergency override, idempotency, status synchronization, search, dashboard counts, and analytics persistence.

## Full workflow demonstration

1. Open **New report** and submit a valid `INSAB1234` / `V01-CRITICAL` report with a six-digit PIN.
2. Confirm inline validation, category, priority, report ID, and assigned handler.
3. Use **User dashboard** to search the report ID and inspect status.
4. Use **Handler desk** to change `Assigned` → `In Progress` → `Resolved`; dispatch load is released when resolved.
5. Use **Routing management** to inspect the zone, primary/backup load, fallback queue and override policy.
6. Use **Analytics** to reconcile category, zone, assignment, resolved and unresolved counts.
7. Try `V77-UNKNOWN`, malformed identifiers, an unknown PIN prefix, and unavailable handlers to demonstrate rejected, correction-queue and capacity paths.

For an isolated, repeatable demo database with synthetic examples across all five categories and key exception paths, follow [DEMO.md](DEMO.md) and run `python scripts/seed_demo.py`.

## Production hardening notes

For a real deployment, put Flask behind a production WSGI server, configure HTTPS, add authentication/role authorization around handler and status mutations, add request rate limits and CSRF protection if cookie-authenticated, validate email and audit actor identity, paginate report queries, add structured logs/metrics, schedule SQLite backups or move to PostgreSQL, and add a background queue worker for retrying queued reports after handler capacity changes.

