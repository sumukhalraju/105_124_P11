"""Deterministic routing-table lookup and capacity-aware dispatch."""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3


ROUTING_TABLE = [
    {"zone_key": "Z1", "zone_name": "North", "pin_prefix": "1", "branch": "North Regulatory Branch", "team": "Alpha", "depot": "Delhi Depot", "authority": "District Officer - North"},
    {"zone_key": "Z2", "zone_name": "North Central", "pin_prefix": "2", "branch": "North Central Regulatory Branch", "team": "Bravo", "depot": "Lucknow Depot", "authority": "District Officer - North Central"},
    {"zone_key": "Z3", "zone_name": "West", "pin_prefix": "3", "branch": "West Regulatory Branch", "team": "Charlie", "depot": "Jaipur Depot", "authority": "District Officer - West"},
    {"zone_key": "Z4", "zone_name": "West Central", "pin_prefix": "4", "branch": "West Central Regulatory Branch", "team": "Delta", "depot": "Mumbai Depot", "authority": "District Officer - West Central"},
    {"zone_key": "Z5", "zone_name": "South", "pin_prefix": "5", "branch": "South Regulatory Branch", "team": "Echo", "depot": "Bengaluru Depot", "authority": "District Officer - South"},
    {"zone_key": "Z6", "zone_name": "East", "pin_prefix": "6", "branch": "East Regulatory Branch", "team": "Foxtrot", "depot": "Kolkata Depot", "authority": "District Officer - East"},
]
ROUTING_BY_ZONE = {row["zone_key"]: row for row in ROUTING_TABLE}


def resolve_zone(pin_code: str) -> dict | None:
    digits = "".join(ch for ch in str(pin_code or "") if ch.isdigit())
    if len(digits) != 6:
        return None
    return next((row for row in ROUTING_TABLE if row["pin_prefix"] == digits[0]), None)


def _handler_loads(conn: sqlite3.Connection) -> dict[int, int]:
    rows = conn.execute("SELECT handler_id, COUNT(*) AS open_cases FROM dispatches WHERE assignment_status IN ('Assigned', 'In Progress') GROUP BY handler_id").fetchall()
    return {row["handler_id"]: row["open_cases"] for row in rows if row["handler_id"] is not None}


def _eligible_handlers(conn: sqlite3.Connection, zone_key: str | None, critical: bool, loads: dict[int, int]) -> list[sqlite3.Row]:
    rows = conn.execute("SELECT * FROM handlers WHERE available = 1 ORDER BY id").fetchall()
    zone_rows = [row for row in rows if zone_key and row["zone_key"] == zone_key]
    # Critical work can use the priority pool across zones after preferring the local zone.
    pool = zone_rows + ([row for row in rows if row not in zone_rows] if critical else [])
    def sort_key(row: sqlite3.Row) -> tuple:
        load = loads.get(row["id"], 0)
        role_order = 0 if row["role"] == "District Officer" else 1
        local_order = 0 if zone_key and row["zone_key"] == zone_key else 1
        return (local_order, load, role_order, row["id"])
    return [row for row in sorted(pool, key=sort_key) if loads.get(row["id"], 0) < min(row["capacity"], 10)]


def dispatch_report(conn: sqlite3.Connection, report: sqlite3.Row) -> dict:
    """Persist exactly one routing decision for a validated report."""
    existing = conn.execute("SELECT * FROM dispatches WHERE report_id = ?", (report["id"],)).fetchone()
    if existing:
        return dict(existing)
    route = resolve_zone(report["pin_code"])
    critical = report["category"] == "Critical" or report["urgency"] == "Critical"
    now = datetime.now(timezone.utc).isoformat()
    if route is None:
        decision = "Central correction queue: unknown PIN zone or routing key."
        conn.execute("INSERT INTO dispatches (report_id, assignment_status, decision, priority, routed_at) VALUES (?, 'Queued', ?, ?, ?)", (report["id"], decision, report["priority"], now))
        conn.execute("UPDATE reports SET status = 'Pending' WHERE id = ?", (report["id"],))
        return dict(conn.execute("SELECT * FROM dispatches WHERE report_id = ?", (report["id"],)).fetchone())

    loads = _handler_loads(conn)
    candidates = _eligible_handlers(conn, route["zone_key"], critical, loads)
    handler = candidates[0] if candidates else None
    if handler:
        assignment_status = "Assigned"
        status = "Assigned"
        decision = "Critical priority override" if critical and handler["zone_key"] != route["zone_key"] else "Primary/backup capacity check passed"
        conn.execute("INSERT INTO dispatches (report_id, zone_key, branch, team, depot, authority, handler_id, assignment_status, decision, priority, routed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (report["id"], route["zone_key"], route["branch"], route["team"], route["depot"], route["authority"], handler["id"], assignment_status, decision, report["priority"], now))
        conn.execute("UPDATE reports SET status = ? WHERE id = ?", (status, report["id"]))
    else:
        assignment_status = "Queued"
        status = "Pending"
        decision = "All eligible handlers are unavailable or at the 10-case capacity limit."
        conn.execute("INSERT INTO dispatches (report_id, zone_key, branch, team, depot, authority, assignment_status, decision, priority, routed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (report["id"], route["zone_key"], route["branch"], route["team"], route["depot"], route["authority"], assignment_status, decision, report["priority"], now))
        conn.execute("UPDATE reports SET status = ? WHERE id = ?", (status, report["id"]))
    return dict(conn.execute("SELECT * FROM dispatches WHERE report_id = ?", (report["id"],)).fetchone())

