from tests.conftest import payload


def test_health_and_validation_spec(client):
    assert client.get("/api/health").get_json()["status"] == "ok"
    spec = client.get("/api/validation/spec").get_json()
    assert len(spec["categories"]) == 5
    assert spec["inspector_id"] == "INS[A-Z]{2}[0-9]{4}"


def test_valid_report_runs_end_to_end_and_is_persisted(client):
    response = client.post("/api/reports", json=payload())
    assert response.status_code == 201
    report = response.get_json()
    assert report["validation_status"] == "accepted"
    assert report["category"] == "Critical"
    assert report["assignment_status"] == "Assigned"
    assert report["handler_name"]
    assert report["status_history"][-1]["to_status"] in {"Assigned", "Pending"}
    assert client.get(f"/api/reports/{report['id']}").get_json()["id"] == report["id"]


def test_missing_fields_and_non_object_json_are_rejected(client):
    assert client.post("/api/reports", json={}).status_code == 400
    assert client.post("/api/reports", json=["not", "an", "object"]).status_code == 400


def test_invalid_identifiers_are_stored_as_rejected_without_dispatch(client):
    response = client.post("/api/reports", json=payload(inspector_id="bad", violation_code="V01-"))
    assert response.status_code == 201
    report = response.get_json()
    assert report["validation_status"] == "rejected"
    assert report["status"] == "Rejected"
    assert report["dispatch_id"] is None
    assert "Inspector ID" in report["validation_message"]


def test_malformed_pin_is_rejected_and_urgency_is_validated(client):
    assert client.post("/api/reports", json=payload(pin_code="56-001")).get_json()["validation_status"] == "rejected"
    assert client.post("/api/reports", json=payload(urgency="Urgent")).status_code == 400


def test_unknown_zone_is_sent_to_central_correction_queue(client):
    report = client.post("/api/reports", json=payload(pin_code="900001")).get_json()
    assert report["assignment_status"] == "Queued"
    assert report["handler_id"] is None
    assert "correction queue" in report["decision"]


def test_idempotency_key_prevents_duplicate_assignments(client):
    first = client.post("/api/reports", json=payload(idempotency_key="submission-1"))
    second = client.post("/api/reports", json=payload(idempotency_key="submission-1"))
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True
    assert second.get_json()["id"] == first.get_json()["id"]


def test_all_six_routing_zones_are_exposed(client):
    routing = client.get("/api/routing").get_json()["routing_table"]
    assert [item["zone_key"] for item in routing] == ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]


def test_handler_capacity_and_availability_are_enforced(client):
    handlers = client.get("/api/handlers").get_json()["handlers"]
    handler = handlers[0]
    assert client.patch(f"/api/handlers/{handler['id']}", json={"capacity": 0}).status_code == 400
    assert client.patch(f"/api/handlers/{handler['id']}", json={"available": "not-a-number"}).status_code == 400
    updated = client.patch(f"/api/handlers/{handler['id']}", json={"available": 0, "capacity": 5}).get_json()["handler"]
    assert updated["available"] == 0 and updated["capacity"] == 5


def test_emergency_priority_sets_p1_and_uses_emergency_pool(client):
    report = client.post("/api/reports", json=payload(violation_code="V02-MAJOR", urgency="Emergency", description="Expired food stock." )).get_json()
    assert report["priority"] == 1
    assert report["assignment_status"] == "Assigned"


def test_status_update_synchronizes_dispatch_and_history(client):
    report = client.post("/api/reports", json=payload()).get_json()
    updated = client.patch(f"/api/reports/{report['id']}/status", json={"status": "In Progress"}).get_json()
    assert updated["status"] == "In Progress"
    assert updated["assignment_status"] == "In Progress"
    resolved = client.patch(f"/api/reports/{report['id']}/status", json={"status": "Resolved"}).get_json()
    assert resolved["status"] == "Resolved"
    assert resolved["assignment_status"] == "Resolved"
    assert len(resolved["status_history"]) == 4


def test_capacity_overflow_queues_when_primary_and_backup_are_unavailable(client):
    handlers = [h for h in client.get("/api/handlers").get_json()["handlers"] if h["zone_key"] == "Z5"]
    for handler in handlers:
        client.patch(f"/api/handlers/{handler['id']}", json={"available": 0})
    report = client.post("/api/reports", json=payload(pin_code="560001", violation_code="V02-MAJOR", description="Expired food stock.")).get_json()
    assert report["assignment_status"] == "Queued"
    assert report["status"] == "Pending"


def test_dashboard_stats_and_analytics_return_persisted_counts(client):
    client.post("/api/reports", json=payload())
    client.post("/api/reports", json=payload(violation_code="V05-PASSED", description="Compliant and satisfactory."))
    stats = client.get("/api/dashboard/stats").get_json()
    analytics = client.get("/api/analytics").get_json()
    assert stats["total"] == 2
    assert sum(item["value"] for item in analytics["by_category"]) == 2
    assert sum(item["value"] for item in analytics["by_zone"]) == 2


def test_report_search_and_status_filter(client):
    report = client.post("/api/reports", json=payload(inspector_id="INSCD5678")).get_json()
    assert len(client.get("/api/reports?search=INSCD5678").get_json()["reports"]) == 1
    assert len(client.get("/api/reports?status=Assigned").get_json()["reports"]) >= 1
    assert client.get(f"/api/reports/{report['id']}").status_code == 200
    assert client.get("/api/reports/not-found").status_code == 404

