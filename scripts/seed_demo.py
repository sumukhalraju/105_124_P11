"""Populate an isolated, repeatable demo database with representative cases."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


DEMO_REPORTS = [
    {"reporter_name": "Asha Demo", "reporter_email": "asha.demo@example.gov", "inspector_id": "INSAB1234", "violation_code": "V01-CRITICAL", "pin_code": "560001", "description": "Critical contamination risk observed near raw meat storage.", "urgency": "Emergency"},
    {"reporter_name": "Ravi Demo", "reporter_email": "ravi.demo@example.gov", "inspector_id": "INSCD2345", "violation_code": "V02-MAJOR", "pin_code": "110001", "description": "Major hygiene violation and unsafe food handling.", "urgency": "High"},
    {"reporter_name": "Mina Demo", "reporter_email": "mina.demo@example.gov", "inspector_id": "INSEF3456", "violation_code": "V03-MINOR", "pin_code": "226001", "description": "Minor label and storage issue.", "urgency": "Medium"},
    {"reporter_name": "Dev Demo", "reporter_email": "dev.demo@example.gov", "inspector_id": "INSGH4567", "violation_code": "V04-ADVISORY", "pin_code": "302001", "description": "Advisory observation; staff training is recommended.", "urgency": "Low"},
    {"reporter_name": "Leela Demo", "reporter_email": "leela.demo@example.gov", "inspector_id": "INSJK5678", "violation_code": "V05-PASSED", "pin_code": "400001", "description": "Compliant, satisfactory inspection; no violation found.", "urgency": "Low"},
    {"reporter_name": "Omar Demo", "reporter_email": "omar.demo@example.gov", "inspector_id": "INSLM6789", "violation_code": "V06-CRITICAL", "pin_code": "700001", "description": "Critical pest infestation in food preparation area.", "urgency": "High"},
    {"reporter_name": "Nila Demo", "reporter_email": "nila.demo@example.gov", "inspector_id": "INSNP7890", "violation_code": "V77-MAJOR", "pin_code": "900001", "description": "Major expired stock found; district zone needs correction.", "urgency": "High"},
    {"reporter_name": "Ira Demo", "reporter_email": "ira.demo@example.gov", "inspector_id": "BAD-ID", "violation_code": "V08-MINOR", "pin_code": "123456", "description": "Malformed inspector identifier demonstration.", "urgency": "Low"},
]


def main() -> None:
    demo_db = ROOT / "instance" / "demo.db"
    app = create_app({"TESTING": True, "DATABASE": str(demo_db)})
    with app.test_client() as client:
        created = 0
        existing = 0
        for index, report in enumerate(DEMO_REPORTS, start=1):
            result = client.post("/api/reports", json={**report, "idempotency_key": f"fieldsafe-demo-v1-{index}"})
            if result.status_code == 201:
                created += 1
            elif result.status_code == 200 and result.get_json().get("duplicate"):
                existing += 1
            else:
                raise SystemExit(f"Could not seed demo report {index}: HTTP {result.status_code} {result.get_data(as_text=True)}")
    print(f"Demo database: {demo_db}")
    print(f"Reports created: {created}; already present: {existing}")
    print("Start the demo with: $env:DATABASE='instance/demo.db'; python app.py")


if __name__ == "__main__":
    main()
