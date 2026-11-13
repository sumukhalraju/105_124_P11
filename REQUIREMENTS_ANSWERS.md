# P11 Food Safety Inspection Portal — Answers to the Problem Statement

This file answers the numbered requirements in the supplied photographs and describes how the implementation satisfies each one. The runnable system and its architecture are documented in [DOC.md](DOC.md); the seeded demonstration steps are in [DEMO.md](DEMO.md).

## Part A — BCS503: Automata Theory and Computability

### 1. DFA and regular expressions for the structured identifiers

**Inspector ID:** The required language is the literal prefix `INS`, followed by exactly two uppercase English letters and exactly four decimal digits.

```text
Regular expression: ^INS[A-Z]{2}[0-9]{4}$
Example accepted:   INSAB1234
Examples rejected:  INSAB123, insAB1234, INSA12345, INS-AB1234
```

The deterministic finite automaton has start state `q0`; it consumes `I`, `N`, `S` in that order, then any uppercase letter in each of two positions, then a digit in each of four positions. Only the state reached after the eighth character (`q9`) is accepting. Every missing, extra, or unsupported character transitions to rejection.

| State | Required next input | Next state |
| --- | --- | --- |
| q0 | `I` | q1 |
| q1 | `N` | q2 |
| q2 | `S` | q3 |
| q3 | `[A-Z]` | q4 |
| q4 | `[A-Z]` | q5 |
| q5 | `[0-9]` | q6 |
| q6 | `[0-9]` | q7 |
| q7 | `[0-9]` | q8 |
| q8 | `[0-9]` | q9 (accept) |

**Violation code:** The implemented structured language is `V`, two digits, a hyphen, and a category token beginning with an uppercase letter and optionally followed by uppercase letters, digits, or underscores.

```text
Regular expression: ^V[0-9]{2}-[A-Z][A-Z0-9_]*$
Example accepted:   V01-CRITICAL
Example accepted:   V99-ADVISORY_2
Examples rejected:  V1-CRITICAL, V01-critical, V01-, X01-MAJOR
```

The DFA consumes `V`, two digits, `-`, and at least one uppercase letter. Once the first category letter has been consumed, the accepting category state loops on `[A-Z0-9_]`. All other inputs reject. Both DFAs are implemented independently from the corresponding Python regular expressions in `portal/validation.py`.

### 2. Implement and compare DFA and regex validation

`validate_identifiers()` runs the DFA and regex validators independently for both fields and returns each result plus an `agreement` flag. A report passes identifier validation only when both approaches accept both identifiers and agree. The tests include representative accepted and rejected values and assert DFA/regex agreement.

### 3. Classify accepted reports into exactly five categories

The supported categories and numeric priorities are:

| Category | Priority |
| --- | ---: |
| Critical | 1 |
| Major | 2 |
| Minor | 3 |
| Advisory | 4 |
| Passed | 5 |

The category token after the violation-code hyphen must map to one of these categories. The description is also checked for category patterns. When several patterns match, the deterministic precedence is **Critical > Major > Minor > Advisory > Passed**. An unknown or unmapped token is rejected with a meaningful reason; it is never silently changed to a supported category. The selected category and explanation are persisted with the report.

### 4. Validation and classification edge cases

- Missing required fields receive a `400` response listing missing fields.
- Malformed inspector IDs, violation codes, or PIN codes are stored as rejected reports with validation reasons and no dispatch.
- Unknown category tokens are rejected with an explicit unmapped-code reason.
- Conflicting category patterns use the documented precedence above.
- Identifier validation stores the independent DFA and regex outcomes and their agreement in the submission response; the report stores the final validation outcome and message.

## Part B — BCS502: Computer Networks

### 5. Routing/dispatch table and capacity policy

The routing table is explicit in `portal/dispatch.py` and exposed by `GET /api/routing`.

| Zone | PIN first digit | Branch | Team | Depot | District authority |
| --- | ---: | --- | --- | --- | --- |
| Z1 North | 1 | North Regulatory Branch | Alpha | Delhi Depot | District Officer - North |
| Z2 North Central | 2 | North Central Regulatory Branch | Bravo | Lucknow Depot | District Officer - North Central |
| Z3 West | 3 | West Regulatory Branch | Charlie | Jaipur Depot | District Officer - West |
| Z4 West Central | 4 | West Central Regulatory Branch | Delta | Mumbai Depot | District Officer - West Central |
| Z5 South | 5 | South Regulatory Branch | Echo | Bengaluru Depot | District Officer - South |
| Z6 East | 6 | East Regulatory Branch | Foxtrot | Kolkata Depot | District Officer - East |

Each zone is seeded with a district officer and deputy. Dispatch prefers an available local district officer, then the local deputy, and balances eligible choices by current open load. Each handler is limited to at most 10 open cases, including when a configured capacity is higher. If no eligible handler has capacity, the report waits in the Pending queue. Handler capacity and availability are manageable in the Handler Desk.

### 6. Dispatch algorithm and report statuses

For a validated report, the dispatch service derives the zone from the six-digit PIN, looks up the route table, reads handler availability and open load, and persists the selected handler or queue decision together with the zone route, priority, decision, and UTC timestamp. An idempotency key and unique dispatch-to-report relationship prevent duplicate submissions/assignments; report creation uses a SQLite immediate transaction to serialize allocation checks.

The lifecycle is `Pending → Assigned → In Progress → Resolved`. Allowed transitions are checked by the API; every transition is added to `status_history`. Resolving work changes the dispatch assignment to Resolved, releasing the handler's open-case capacity.

### 7. Exceptional routing and dispatch scenarios

- **Unknown zone:** a valid six-digit PIN outside the configured prefixes is routed to the Central correction queue and remains Pending.
- **Malformed identifiers or PIN:** rejected before dispatch, with an explanatory validation message.
- **Unavailable or full handlers:** dispatch uses the eligible local deputy/backup; when no eligible handler is available it records a queued decision.
- **Priority override:** Critical classification or Emergency urgency promotes work into the emergency pool. The allocator prefers the local zone and can select an available handler from another zone when necessary; the decision is recorded.
- **Simultaneous or repeated submissions:** report creation is serialized in SQLite, and a caller-supplied idempotency key returns the original report on retry. Dispatch rows are unique per report.

## Part C — Frontend and Web Application Development

### 8. Responsive web application and selected stack

The photographs mention a MERN stack and also explicitly require a Flask backend integrated with SQLite. The implementation follows the more specific integration requirement: Flask serves a responsive HTML/CSS/JavaScript client and the JSON API, while SQLite persists reports, handlers, dispatches, and history. This keeps the demonstration deployable as one service without a separate JavaScript server.

### 9. Required interfaces

| Interface | Delivered behavior |
| --- | --- |
| Report Submission | Reporter details, inspector ID, violation code, PIN, description, urgency; DFA/regex validation; category, priority, report ID, route, handler, and outcome feedback. |
| User Dashboard | Total, pending, assigned, in-progress, resolved, rejected, and queued metrics; report search and status filter; clickable report details with validation/classification, routing, assignment, description, and status history; print-to-PDF and JSON/CSV downloads. |
| Handler Dashboard | Roster, zone, role, open cases, availability and capacity controls; assigned-report table with category, priority, handler, submission time, and status updates. |
| Routing Management | Six-zone table; primary/deputy loads and capacity; pending queue count; fallback and critical/emergency override policies. |
| Analytics | Category, zone, and assignment distributions, plus resolved, unresolved, queued, and rejected counts. |

### 10. Integrate frontend, Flask, and SQLite

The browser communicates with Flask JSON endpoints. The backend performs validation, classification, routing, assignment, lifecycle changes, search, dashboard aggregation, and analytics against SQLite. The schema uses foreign keys, uniqueness constraints, enumerated-value checks, and indexes. `create_app()` supports a temporary file-backed database in tests and an environment override via `DATABASE`.

## Part D — Testing and Integration

### 11. Integrate modules into one demonstrable application

Run `python app.py` after installing `requirements.txt`; the browser application is served from `/`, and the JSON API is under `/api`. For a seeded showcase, follow [DEMO.md](DEMO.md). The demo database is separate from the ordinary development database.

### 12. At least 15 test cases

The project currently has **49 automated test cases**, including parameterized cases. They cover:

- Valid and invalid inspector IDs and violation codes, including DFA/regex agreement.
- All five categories, conflicting patterns, and precedence.
- Unknown category rejection and malformed required data/PINs.
- Report submission, database persistence, history, and duplicate idempotency.
- All six routing entries, unknown-zone fallback, handler availability, capacity and emergency priority.
- Status changes and dispatch-load synchronization.
- Search, filters, dashboard totals, and analytics aggregation.

Run them with `python -m pytest -q`. The recorded coverage run reached 92% across `app.py` and the `portal` package.

### 13. Demonstrate the full workflow

1. Submit a report with a valid inspector ID, mapped violation code, and six-digit PIN.
2. Validate both identifiers with the DFA and regex.
3. Classify the report and determine its priority.
4. Resolve the PIN to its zone, consult handler capacity, and assign or queue the report.
5. Find the generated report ID in the User Dashboard.
6. Update status through the Handler Desk and confirm each transition in history and the released handler load after resolution.
7. Inspect routing decisions and zone loads, then reconcile report outcomes in Analytics.

The repeatable demo dataset includes valid examples for every category, an emergency priority case, an unknown-zone correction-queue case, and a malformed-ID rejection case.

## Expected outcome

The project demonstrates an explicit DFA and equivalent regular expressions, exactly five mapped report categories, table-based six-zone routing, capacity-aware assignment and fallback, lifecycle tracking backed by SQLite, responsive operational dashboards, and an automated suite exceeding the 15-test minimum. Start locally with the commands in [DOC.md](DOC.md); use [DEMO.md](DEMO.md) for the seeded presentation flow.
