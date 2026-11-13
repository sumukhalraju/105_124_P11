from pathlib import Path

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path: Path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "portal-test.db")})


@pytest.fixture()
def client(app):
    return app.test_client()


def payload(**overrides):
    value = {
        "reporter_name": "Priya Sharma",
        "reporter_email": "priya@example.gov",
        "inspector_id": "INSAB1234",
        "violation_code": "V01-CRITICAL",
        "pin_code": "560001",
        "description": "Critical contamination risk found near raw meat storage.",
        "urgency": "High",
    }
    value.update(overrides)
    return value

