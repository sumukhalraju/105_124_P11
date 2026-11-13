PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS handlers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    zone_key TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('District Officer', 'Deputy Officer')),
    available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    capacity INTEGER NOT NULL DEFAULT 10 CHECK (capacity BETWEEN 1 AND 10)
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    reporter_name TEXT NOT NULL,
    reporter_email TEXT NOT NULL,
    inspector_id TEXT NOT NULL,
    violation_code TEXT NOT NULL,
    pin_code TEXT NOT NULL,
    description TEXT NOT NULL,
    urgency TEXT NOT NULL CHECK (urgency IN ('Low', 'Medium', 'High', 'Critical')),
    category TEXT NOT NULL CHECK (category IN ('Critical', 'Major', 'Minor', 'Advisory', 'Passed')),
    classification_reason TEXT NOT NULL,
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    validation_status TEXT NOT NULL CHECK (validation_status IN ('accepted', 'rejected')),
    validation_message TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Pending', 'Assigned', 'In Progress', 'Resolved', 'Rejected')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dispatches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL UNIQUE REFERENCES reports(id) ON DELETE CASCADE,
    zone_key TEXT,
    branch TEXT,
    team TEXT,
    depot TEXT,
    authority TEXT,
    handler_id INTEGER REFERENCES handlers(id),
    assignment_status TEXT NOT NULL CHECK (assignment_status IN ('Queued', 'Assigned', 'In Progress', 'Resolved')),
    decision TEXT NOT NULL,
    priority INTEGER NOT NULL,
    routed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    note TEXT,
    changed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_category ON reports(category);
CREATE INDEX IF NOT EXISTS idx_dispatches_zone ON dispatches(zone_key);

