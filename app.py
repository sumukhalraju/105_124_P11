"""Flask application for the Food Safety Inspection Portal."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import uuid

from flask import Flask, jsonify, request, g, send_from_directory

from portal.dispatch import ROUTING_TABLE, dispatch_report
from portal.validation import CATEGORIES, classify_report, validate_identifiers


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "instance" / "portal.db"
SEED_HANDLERS = [
    ("Aarav Menon", "Z1", "District Officer"), ("Nisha Kapoor", "Z1", "Deputy Officer"),
    ("Rohan Iyer", "Z2", "District Officer"), ("Meera Shah", "Z2", "Deputy Officer"),
    ("Kabir Rao", "Z3", "District Officer"), ("Tara Joshi", "Z3", "Deputy Officer"),
    ("Vikram Singh", "Z4", "District Officer"), ("Ananya Das", "Z4", "Deputy Officer"),
    ("Devika Nair", "Z5", "District Officer"), ("Arjun Bhat", "Z5", "Deputy Officer"),
    ("Ishaan Bose", "Z6", "District Officer"), ("Pooja Roy", "Z6", "Deputy Officer"),
]


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_mapping(DATABASE=str(DEFAULT_DB), TESTING=False)
    if test_config:
        app.config.update(test_config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        init_db()

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "food-safety-inspection-portal"})

    @app.get("/api/validation/spec")
    def validation_spec():
        return jsonify({
            "inspector_id": "INS[A-Z]{2}[0-9]{4}",
            "violation_code": "V[0-9]{2}-[A-Z][A-Z0-9_]*",
            "categories": CATEGORIES,
            "priority_order": ["Critical", "Major", "Minor", "Advisory", "Passed"],
        })

    @app.post("/api/reports")
    def create_report():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        required = ("reporter_name", "reporter_email", "inspector_id", "violation_code", "pin_code", "description", "urgency")
        missing = [field for field in required if not str(payload.get(field, "")).strip()]
        if missing:
            return jsonify({"error": "Missing required fields.", "fields": missing}), 400

        db = get_db()
        db.execute("BEGIN IMMEDIATE")
        idempotency_key = str(payload.get("idempotency_key", "")).strip() or None
        if idempotency_key:
            previous = db.execute("SELECT id FROM reports WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
            if previous:
                db.commit()
                return jsonify(report_response(previous["id"], duplicate=True)), 200

        inspector_id = str(payload["inspector_id"]).strip().upper()
        violation_code = str(payload["violation_code"]).strip().upper()
        pin_code = str(payload["pin_code"]).strip()
        urgency = str(payload["urgency"]).strip().title()
        if urgency not in {"Low", "Medium", "High", "Emergency"}:
            return jsonify({"error": "Urgency must be Low, Medium, High, or Emergency."}), 400
        validation = validate_identifiers(inspector_id, violation_code)
        if len(pin_code) != 6 or not pin_code.isdigit():
            validation["valid"] = False
            validation["errors"].append("PIN code must contain exactly six digits.")
            validation["message"] = " ".join(validation["errors"])
        classification = None
        if validation["valid"]:
            classification = classify_report(violation_code, str(payload["description"]).strip())
            if not classification["mapped"]:
                validation["valid"] = False
                validation["errors"].append(classification["reason"])
                validation["message"] = " ".join(validation["errors"])
        report_id = f"FSI-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.now(timezone.utc).isoformat()
        if validation["valid"]:
            category = classification["category"]
            priority = 1 if urgency == "Emergency" else classification["priority"]
            status = "Pending"
            validation_status = "accepted"
            validation_message = validation["message"]
            classification_reason = classification["reason"]
        else:
            category = "Advisory"
            priority = 4
            status = "Rejected"
            validation_status = "rejected"
            validation_message = validation["message"]
            classification_reason = "Classification skipped because one or more identifiers were rejected."

        try:
            db.execute("INSERT INTO reports (id, idempotency_key, reporter_name, reporter_email, inspector_id, violation_code, pin_code, description, urgency, category, classification_reason, priority, validation_status, validation_message, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (report_id, idempotency_key, str(payload["reporter_name"]).strip(), str(payload["reporter_email"]).strip(), inspector_id, violation_code, pin_code, str(payload["description"]).strip(), urgency, category, classification_reason, priority, validation_status, validation_message, status, created_at))
            db.execute("INSERT INTO status_history (report_id, from_status, to_status, note, changed_at) VALUES (?, ?, ?, ?, ?)", (report_id, None, status, "Report submitted", created_at))
            if validation["valid"]:
                report = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
                dispatch_report(db, report)
                latest_status = db.execute("SELECT status FROM reports WHERE id = ?", (report_id,)).fetchone()["status"]
                if latest_status != status:
                    db.execute("INSERT INTO status_history (report_id, from_status, to_status, note, changed_at) VALUES (?, ?, ?, ?, ?)", (report_id, status, latest_status, "Dispatch decision", datetime.now(timezone.utc).isoformat()))
            db.commit()
        except sqlite3.IntegrityError as error:
            db.rollback()
            return jsonify({"error": "Could not persist report.", "detail": str(error)}), 409
        return jsonify(report_response(report_id)), 201

    @app.get("/api/reports")
    def list_reports():
        db = get_db()
        search = str(request.args.get("search", "")).strip()
        status = str(request.args.get("status", "")).strip()
        clauses, args = [], []
        handler_id = request.args.get("handler_id")
        if handler_id:
            try:
                args.append(int(handler_id))
            except ValueError:
                return jsonify({"error": "handler_id must be numeric."}), 400
            clauses.append("d.handler_id = ?")
        if search:
            clauses.append("(r.id LIKE ? OR r.inspector_id LIKE ? OR r.description LIKE ?)")
            args.extend([f"%{search}%"] * 3)
        if status:
            clauses.append("r.status = ?")
            args.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = db.execute(f"SELECT r.id FROM reports r LEFT JOIN dispatches d ON d.report_id = r.id {where} ORDER BY r.priority ASC, r.created_at DESC", args).fetchall()
        return jsonify({"reports": [report_response(row["id"]) for row in rows]})

    @app.get("/api/reports/<report_id>")
    def get_report(report_id):
        if not get_db().execute("SELECT 1 FROM reports WHERE id = ?", (report_id,)).fetchone():
            return jsonify({"error": "Report not found."}), 404
        return jsonify(report_response(report_id))

    @app.patch("/api/reports/<report_id>/status")
    def update_status(report_id):
        payload = request.get_json(silent=True) or {}
        new_status = str(payload.get("status", "")).strip()
        allowed = {"Pending", "Assigned", "In Progress", "Resolved"}
        if new_status not in allowed:
            return jsonify({"error": "Status must be Pending, Assigned, In Progress, or Resolved."}), 400
        db = get_db()
        current = db.execute("SELECT status FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not current:
            return jsonify({"error": "Report not found."}), 404
        transitions = {
            "Pending": {"Pending", "Assigned"},
            "Assigned": {"Assigned", "In Progress", "Resolved"},
            "In Progress": {"In Progress", "Resolved"},
            "Resolved": {"Resolved"},
        }
        if new_status not in transitions.get(current["status"], set()):
            return jsonify({"error": f"Invalid status transition from {current['status']} to {new_status}."}), 409
        now = datetime.now(timezone.utc).isoformat()
        db.execute("UPDATE reports SET status = ? WHERE id = ?", (new_status, report_id))
        dispatch = db.execute("SELECT assignment_status FROM dispatches WHERE report_id = ?", (report_id,)).fetchone()
        if dispatch:
            assignment_status = "In Progress" if new_status == "In Progress" else "Resolved" if new_status == "Resolved" else new_status
            db.execute("UPDATE dispatches SET assignment_status = ? WHERE report_id = ?", (assignment_status, report_id))
        db.execute("INSERT INTO status_history (report_id, from_status, to_status, note, changed_at) VALUES (?, ?, ?, ?, ?)", (report_id, current["status"], new_status, str(payload.get("note", "Status updated")), now))
        db.commit()
        return jsonify(report_response(report_id))

    @app.get("/api/handlers")
    def list_handlers():
        db = get_db()
        rows = db.execute("SELECT h.*, COALESCE(SUM(CASE WHEN d.assignment_status IN ('Assigned', 'In Progress') THEN 1 ELSE 0 END), 0) AS open_cases FROM handlers h LEFT JOIN dispatches d ON d.handler_id = h.id GROUP BY h.id ORDER BY h.zone_key, h.id").fetchall()
        return jsonify({"handlers": [dict(row) for row in rows]})

    @app.patch("/api/handlers/<int:handler_id>")
    def update_handler(handler_id):
        payload = request.get_json(silent=True) or {}
        db = get_db()
        handler = db.execute("SELECT * FROM handlers WHERE id = ?", (handler_id,)).fetchone()
        if not handler:
            return jsonify({"error": "Handler not found."}), 404
        try:
            available = int(payload.get("available", handler["available"]))
            capacity = int(payload.get("capacity", handler["capacity"]))
        except (TypeError, ValueError):
            return jsonify({"error": "Availability and capacity must be numeric."}), 400
        if available not in (0, 1) or not 1 <= capacity <= 10:
            return jsonify({"error": "Availability must be 0/1 and capacity must be between 1 and 10."}), 400
        open_cases = db.execute("SELECT COUNT(*) AS count FROM dispatches WHERE handler_id = ? AND assignment_status IN ('Assigned', 'In Progress')", (handler_id,)).fetchone()["count"]
        if capacity < open_cases:
            return jsonify({"error": f"Capacity cannot be below current open case count ({open_cases})."}), 409
        db.execute("UPDATE handlers SET available = ?, capacity = ? WHERE id = ?", (available, capacity, handler_id))
        db.commit()
        return jsonify({"handler": dict(db.execute("SELECT * FROM handlers WHERE id = ?", (handler_id,)).fetchone())})

    @app.get("/api/routing")
    def routing():
        return jsonify({"routing_table": ROUTING_TABLE, "fallback": "Central correction queue"})

    @app.get("/api/dashboard/stats")
    def dashboard_stats():
        db = get_db()
        counts = {row["status"]: row["count"] for row in db.execute("SELECT status, COUNT(*) AS count FROM reports GROUP BY status").fetchall()}
        return jsonify({"total": sum(counts.values()), "pending": counts.get("Pending", 0), "assigned": counts.get("Assigned", 0), "in_progress": counts.get("In Progress", 0), "resolved": counts.get("Resolved", 0), "rejected": counts.get("Rejected", 0), "queued": db.execute("SELECT COUNT(*) AS count FROM dispatches WHERE assignment_status = 'Queued'").fetchone()["count"]})

    @app.get("/api/analytics")
    def analytics():
        db = get_db()
        by_category = [dict(row) for row in db.execute("SELECT category AS label, COUNT(*) AS value FROM reports GROUP BY category ORDER BY CASE category WHEN 'Critical' THEN 1 WHEN 'Major' THEN 2 WHEN 'Minor' THEN 3 WHEN 'Advisory' THEN 4 WHEN 'Passed' THEN 5 END").fetchall()]
        by_zone = [dict(row) for row in db.execute("SELECT COALESCE(d.zone_key, 'Fallback') AS label, COUNT(*) AS value FROM reports r LEFT JOIN dispatches d ON d.report_id = r.id GROUP BY COALESCE(d.zone_key, 'Fallback') ORDER BY label").fetchall()]
        by_assignment = [dict(row) for row in db.execute("SELECT assignment_status AS label, COUNT(*) AS value FROM dispatches GROUP BY assignment_status ORDER BY label").fetchall()]
        return jsonify({"by_category": by_category, "by_zone": by_zone, "by_assignment": by_assignment})

    return app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app_config()["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def current_app_config():
    # Import lazily avoids exposing Flask globals in domain modules.
    from flask import current_app
    return current_app.config


def init_db():
    db = get_db()
    schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)
    if db.execute("SELECT COUNT(*) AS count FROM handlers").fetchone()["count"] == 0:
        db.executemany("INSERT INTO handlers (name, zone_key, role, available, capacity) VALUES (?, ?, ?, 1, 10)", SEED_HANDLERS)
    db.commit()


def report_response(report_id: str, duplicate: bool = False) -> dict:
    db = get_db()
    row = db.execute("SELECT r.*, d.id AS dispatch_id, d.zone_key, d.branch, d.team, d.depot, d.authority, d.handler_id, d.assignment_status, d.decision, d.routed_at, h.name AS handler_name FROM reports r LEFT JOIN dispatches d ON d.report_id = r.id LEFT JOIN handlers h ON h.id = d.handler_id WHERE r.id = ?", (report_id,)).fetchone()
    if not row:
        return {"error": "Report not found."}
    result = dict(row)
    result["duplicate"] = duplicate
    result["status_history"] = [dict(item) for item in db.execute("SELECT from_status, to_status, note, changed_at FROM status_history WHERE report_id = ? ORDER BY id", (report_id,)).fetchall()]
    return result


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)

