# File: test_workflow.py
# Description: Verifies agency boundaries, referral transitions, and atomic history.
# Author: Michael Burns <mdburnsjr@gmail.com>
# Created: 2026-10-08
# Last Modified: 2026-10-08 by Michael Burns
# Dependencies: pytest, fastapi, httpx, sqlite3, backend.database, backend.main

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.database import connect
from backend.main import create_app

CASE_BODY = {"title": "Fictional resource request", "summary": "Synthetic request for community support.", "priority": "high"}


def identity(user_id: int):
    return {"X-Demo-User-Id": str(user_id)}


@pytest.fixture
def environment(tmp_path):
    database_path = tmp_path / "workflow.sqlite3"
    with TestClient(create_app(database_path)) as client:
        yield client, database_path


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/cases", None),
    ("GET", "/api/cases/1001", None),
    ("GET", "/api/cases/1001/audit-events", None),
    ("GET", "/api/referrals/inbox", None),
    ("GET", "/api/analytics/referrals", None),
    ("POST", "/api/cases", CASE_BODY),
    ("PATCH", "/api/cases/1001", {"priority": "low"}),
    ("POST", "/api/cases/1001/referrals", {"to_agency_id": 2}),
    ("PATCH", "/api/referrals/1", {"status": "accepted"}),
])
def test_missing_identity_is_rejected(environment, method, path, body):
    client, _ = environment
    assert client.request(method, path, json=body).status_code == 401


def test_unknown_user_and_directory(environment):
    client, _ = environment
    assert client.get("/api/cases", headers=identity(999)).status_code == 401
    assert len(client.get("/api/demo-users").json()) == 3
    assert len(client.get("/api/agencies").json()) == 3


def test_entire_referral_story_and_history(environment):
    client, _ = environment
    created = client.post("/api/cases", json=CASE_BODY, headers=identity(1))
    assert created.status_code == 201
    case_id = created.json()["id"]
    path = f"/api/cases/{case_id}"
    assert created.json()["owner_agency_id"] == 1
    assert client.get(path, headers=identity(2)).status_code == 404

    sent = client.post(path + "/referrals", json={"to_agency_id": 2}, headers=identity(1))
    assert sent.status_code == 201
    referral_path = f"/api/referrals/{sent.json()['id']}"
    assert client.get(path, headers=identity(2)).status_code == 200
    assert case_id in [row["id"] for row in client.get("/api/cases", headers=identity(2)).json()]
    assert client.get("/api/referrals/inbox", headers=identity(2)).json()[0]["case_id"] == case_id
    assert client.get("/api/referrals/inbox", headers=identity(1)).json() == []

    # Owning a case does not grant the right to accept someone else's referral.
    assert client.patch(referral_path, json={"status": "accepted"}, headers=identity(1)).status_code == 404
    assert client.patch(referral_path, json={"status": "completed"}, headers=identity(2)).status_code == 409
    assert client.patch(referral_path, json={"status": "accepted"}, headers=identity(2)).status_code == 200
    assert client.patch(referral_path, json={"status": "accepted"}, headers=identity(2)).status_code == 200
    assert client.patch(referral_path, json={"status": "pending"}, headers=identity(2)).status_code == 409
    assert client.patch(referral_path, json={"status": "completed"}, headers=identity(2)).status_code == 200
    assert client.patch(referral_path, json={"status": "accepted"}, headers=identity(2)).status_code == 409

    # Completion retains read access, as specified by this prototype's policy.
    detail = client.get(path, headers=identity(2)).json()
    assert detail["referrals"][0]["status"] == "completed"
    assert [event["action"] for event in detail["events"]] == [
        "Completed referral for Public Safety", "Accepted referral for Public Safety",
        "Referred case to Public Safety", "Created case",
    ]
    assert detail["events"][0]["actor_name"] == "Jordan Lee"
    assert client.get(path + "/audit-events", headers=identity(1)).json() == detail["events"]

    # A third agency cannot discover the case, its timeline, or referral content.
    assert client.get(path, headers=identity(3)).status_code == 404
    assert client.get(path + "/audit-events", headers=identity(3)).status_code == 404
    assert client.patch(referral_path, json={"status": "completed"}, headers=identity(3)).status_code == 404
    assert case_id not in [row["id"] for row in client.get("/api/cases", headers=identity(3)).json()]


def test_recipients_cannot_edit_or_reshare(environment):
    client, _ = environment
    client.post("/api/cases/1001/referrals", json={"to_agency_id": 2}, headers=identity(1))
    assert client.patch("/api/cases/1001", json={"priority": "low"}, headers=identity(2)).status_code == 403
    assert client.post("/api/cases/1001/referrals", json={"to_agency_id": 3}, headers=identity(2)).status_code == 403
    assert client.patch("/api/cases/1001", json={"priority": "low"}, headers=identity(3)).status_code == 404
    assert client.post("/api/cases/1001/referrals", json={"to_agency_id": 2}, headers=identity(3)).status_code == 404
    response = client.patch("/api/cases/1001", json={"priority": "low"}, headers=identity(1))
    assert response.status_code == 200
    assert response.json()["priority"] == "low"
    client.patch("/api/cases/1001", json={"priority": "low"}, headers=identity(1))
    assert len(client.get("/api/cases/1001/audit-events", headers=identity(1)).json()) == 2


@pytest.mark.parametrize("override", [
    {"title": "   "}, {"summary": "short"}, {"priority": "urgent"},
    {"owner_agency_id": 2}, {"title": "x" * 121},
])
def test_create_validation_and_ownership_spoofing(environment, override):
    client, _ = environment
    response = client.post("/api/cases", json={**CASE_BODY, **override}, headers=identity(1))
    assert response.status_code == 422
    assert len(client.get("/api/cases", headers=identity(1)).json()) == 2


def test_duplicate_and_invalid_recipients(environment):
    client, _ = environment
    path = "/api/cases/1001/referrals"
    for recipient in (1, 999):
        assert client.post(path, json={"to_agency_id": recipient}, headers=identity(1)).status_code == 422
    assert client.post(path, json={"to_agency_id": 2}, headers=identity(1)).status_code == 201
    assert client.post(path, json={"to_agency_id": 2}, headers=identity(1)).status_code == 409
    assert len(client.get("/api/cases/1001/audit-events", headers=identity(1)).json()) == 1


def test_report_includes_zero_counts_and_excludes_other_owners(environment):
    client, _ = environment
    sent = client.post("/api/cases/1001/referrals", json={"to_agency_id": 2}, headers=identity(1)).json()
    client.post("/api/cases/1003/referrals", json={"to_agency_id": 2}, headers=identity(3))
    report = client.get("/api/analytics/referrals", headers=identity(1)).json()
    assert [(row["agency_id"], row["pending_referrals"]) for row in report] == [(1, 0), (2, 1), (3, 0)]
    # Receiving agencies cannot use this report to inspect other owners' totals.
    assert all(row["pending_referrals"] == 0 for row in client.get("/api/analytics/referrals", headers=identity(2)).json())
    client.patch(f"/api/referrals/{sent['id']}", json={"status": "accepted"}, headers=identity(2))
    assert all(row["pending_referrals"] == 0 for row in client.get("/api/analytics/referrals", headers=identity(1)).json())


@pytest.mark.parametrize("operation", ["create", "refer", "priority", "accept"])
def test_audit_failure_rolls_back_mutation(environment, operation):
    client, database_path = environment
    referral_id = None
    if operation == "accept":
        referral_id = client.post("/api/cases/1001/referrals", json={"to_agency_id": 2}, headers=identity(1)).json()["id"]
    with connect(database_path) as connection, connection:
        # Force a real database failure. No change may survive a failed audit write.
        connection.execute("""CREATE TRIGGER reject_audit BEFORE INSERT ON audit_events
                              BEGIN SELECT RAISE(ABORT, 'Simulated audit failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        if operation == "create":
            client.post("/api/cases", json=CASE_BODY, headers=identity(1))
        elif operation == "refer":
            client.post("/api/cases/1001/referrals", json={"to_agency_id": 2}, headers=identity(1))
        elif operation == "priority":
            client.patch("/api/cases/1001", json={"priority": "low"}, headers=identity(1))
        else:
            client.patch(f"/api/referrals/{referral_id}", json={"status": "accepted"}, headers=identity(2))
    with connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 4
        assert connection.execute("SELECT priority FROM cases WHERE id = 1001").fetchone()[0] == "high"
        referrals = connection.execute("SELECT status FROM referrals").fetchall()
        assert [row[0] for row in referrals] == (["pending"] if operation == "accept" else [])
