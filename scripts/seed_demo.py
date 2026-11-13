"""Populate an isolated, repeatable demo database with representative cases."""

from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


DEMO_REPORTS = [
    {"reporter_name": "Asha Demo", "reporter_email": "asha.demo@example.gov", "inspector_id": "INSAB1234", "violation_code": "V01-CRITICAL", "pin_code": "560001", "description": "Critical contamination risk observed near raw meat storage.", "urgency": "Critical"},
    {"reporter_name": "Ravi Demo", "reporter_email": "ravi.demo@example.gov", "inspector_id": "INSCD2345", "violation_code": "V02-MAJOR", "pin_code": "110001", "description": "Major hygiene violation and unsafe food handling.", "urgency": "High"},
    {"reporter_name": "Mina Demo", "reporter_email": "mina.demo@example.gov", "inspector_id": "INSEF3456", "violation_code": "V03-MINOR", "pin_code": "226001", "description": "Minor label and storage issue.", "urgency": "Medium"},
    {"reporter_name": "Dev Demo", "reporter_email": "dev.demo@example.gov", "inspector_id": "INSGH4567", "violation_code": "V04-ADVISORY", "pin_code": "302001", "description": "Advisory observation; staff training is recommended.", "urgency": "Low"},
    {"reporter_name": "Leela Demo", "reporter_email": "leela.demo@example.gov", "inspector_id": "INSJK5678", "violation_code": "V05-PASSED", "pin_code": "400001", "description": "Compliant, satisfactory inspection; no violation found.", "urgency": "Low"},
    {"reporter_name": "Omar Demo", "reporter_email": "omar.demo@example.gov", "inspector_id": "INSLM6789", "violation_code": "V06-CRITICAL", "pin_code": "700001", "description": "Critical pest infestation in food preparation area.", "urgency": "High"},
    {"reporter_name": "Nila Demo", "reporter_email": "nila.demo@example.gov", "inspector_id": "INSNP7890", "violation_code": "V77-MAJOR", "pin_code": "900001", "description": "Major expired stock found; district zone needs correction.", "urgency": "High"},
    {"reporter_name": "Ira Demo", "reporter_email": "ira.demo@example.gov", "inspector_id": "BAD-ID", "violation_code": "V08-MINOR", "pin_code": "123456", "description": "Malformed inspector identifier demonstration.", "urgency": "Low"},
    {"reporter_name": "Noah Demo", "reporter_email": "noah.demo@example.gov", "inspector_id": "INSQR8901", "violation_code": "V09-MAJOR", "pin_code": "680001", "description": "Major temperature-control failure in chilled storage.", "urgency": "High"},
    {"reporter_name": "Sara Demo", "reporter_email": "sara.demo@example.gov", "inspector_id": "INSTU9012", "violation_code": "V10-ADVISORY", "pin_code": "520001", "description": "Advisory staff-training follow-up is recommended.", "urgency": "Low"},
    {"reporter_name": "Kiran Demo", "reporter_email": "kiran.demo@example.gov", "inspector_id": "INSVW0123", "violation_code": "V11-MAJOR", "pin_code": "610001", "description": "Major unsafe food-storage temperature deviation.", "urgency": "High"},
    {"reporter_name": "Amara Demo", "reporter_email": "amara.demo@example.gov", "inspector_id": "INSXY1234", "violation_code": "V12-MINOR", "pin_code": "120001", "description": "Minor documentation gap in cleaning log.", "urgency": "Medium"},
    {"reporter_name": "Neil Demo", "reporter_email": "neil.demo@example.gov", "inspector_id": "INSZA2345", "violation_code": "V13-ADVISORY", "pin_code": "230001", "description": "Advisory guidance for staff handwashing training.", "urgency": "Low"},
    {"reporter_name": "Rhea Demo", "reporter_email": "rhea.demo@example.gov", "inspector_id": "INSBC3456", "violation_code": "V14-PASSED", "pin_code": "340001", "description": "Passed inspection, compliant and satisfactory.", "urgency": "Low"},
    {"reporter_name": "Tomas Demo", "reporter_email": "tomas.demo@example.gov", "inspector_id": "INSDE4567", "violation_code": "V15-MAJOR", "pin_code": "450001", "description": "Major cross-contamination concern in prep area.", "urgency": "High"},
    {"reporter_name": "Zoya Demo", "reporter_email": "zoya.demo@example.gov", "inspector_id": "INSFG5678", "violation_code": "V16-CRITICAL", "pin_code": "560002", "description": "Critical allergen cross-contact risk identified.", "urgency": "Critical"},
    {"reporter_name": "Evan Demo", "reporter_email": "evan.demo@example.gov", "inspector_id": "INSHI6789", "violation_code": "V17-MINOR", "pin_code": "670001", "description": "Minor product-label correction needed.", "urgency": "Medium"},
    {"reporter_name": "Maya Demo", "reporter_email": "maya.demo@example.gov", "inspector_id": "INSJK7890", "violation_code": "V18-ADVISORY", "pin_code": "180001", "description": "Advisory recommendation for routine staff refresher training.", "urgency": "Low"},
]


def capacity_demo_reports() -> list[dict]:
    """Return reproducible pseudo-random open cases spread across all six zones."""
    rng = random.Random(20261113)
    reports = []
    for zone_number in range(1, 7):
        for slot in range(1, 2):
            letters = f"{chr(64 + zone_number)}{chr(75 + slot)}"
            inspector_number = 8000 + zone_number * 10 + slot
            category = rng.choice(["MINOR", "MAJOR", "ADVISORY"])
            descriptions = {
                "MINOR": "Minor storage observation used to demonstrate open handler capacity.",
                "MAJOR": "Major hygiene follow-up used to demonstrate open handler capacity.",
                "ADVISORY": "Advisory staff guidance used to demonstrate open handler capacity.",
            }
            reports.append({
                "reporter_name": f"Capacity Demo Z{zone_number}-{slot}",
                "reporter_email": f"capacity.z{zone_number}.{slot}@example.gov",
                "inspector_id": f"INS{letters}{inspector_number}",
                "violation_code": f"V19-{category}",
                "pin_code": f"{zone_number}80001",
                "description": f"{descriptions[category]} in zone Z{zone_number}.",
                "urgency": "Medium",
            })
    return reports


def main() -> None:
    demo_db = ROOT / "instance" / "demo.db"
    app = create_app({"TESTING": True, "DATABASE": str(demo_db)})
    with app.test_client() as client:
        created = 0
        existing = 0
        reports = DEMO_REPORTS + capacity_demo_reports()
        for index, report in enumerate(reports, start=1):
            key = f"fieldsafe-demo-v1-{index}" if index <= len(DEMO_REPORTS) else f"fieldsafe-capacity-v1-{report['inspector_id']}"
            result = client.post("/api/reports", json={**report, "idempotency_key": key})
            if result.status_code == 201:
                created += 1
            elif result.status_code == 200 and result.get_json().get("duplicate"):
                existing += 1
            else:
                raise SystemExit(f"Could not seed demo report {index}: HTTP {result.status_code} {result.get_data(as_text=True)}")
            report_data = result.get_json()
            desired_status = {2: "In Progress", 3: "Resolved", 11: "In Progress", 12: "Resolved"}.get(index)
            if desired_status and report_data.get("status") != desired_status:
                update = client.patch(f"/api/reports/{report_data['id']}/status", json={"status": desired_status, "note": "Seeded demo lifecycle example"})
                if update.status_code != 200:
                    raise SystemExit(f"Could not set demo report {index} to {desired_status}: {update.get_data(as_text=True)}")
    print(f"Demo database: {demo_db}")
    print(f"Reports created: {created}; already present: {existing}; base samples: {len(DEMO_REPORTS)}; capacity cases: {len(capacity_demo_reports())}")
    print("Start the demo with: $env:DATABASE='instance/demo.db'; python app.py")


if __name__ == "__main__":
    main()
