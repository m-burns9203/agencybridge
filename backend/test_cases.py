# File: test_cases.py
# Description: Checks real API responses, filtering, and database integrity.
# Author: Michael Burns <mdburnsjr@gmail.com>
# Created: 2026-10-08
# Last Modified: 2026-10-08 by Michael Burns
# Dependencies: pytest, fastapi, httpx, sqlite3, backend.main, backend.database

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.database import connect, initialize_database
from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    """Use a disposable database so tests cannot alter the user's demo data."""
    with TestClient(create_app(tmp_path / "test.sqlite3")) as test_client:
        test_client.headers["X-Demo-User-Id"] = "1"
        yield test_client


def test_list_joins_agencies_and_orders_newest_first(client):
    response = client.get("/api/cases")
    assert response.status_code == 200
    cases = response.json()
    assert [case["id"] for case in cases] == [1004, 1001]
    assert cases[0]["agency_name"] == "Community Services"


def test_filter_and_invalid_priority(client):
    response = client.get("/api/cases?priority=high")
    assert response.status_code == 200
    assert [case["id"] for case in response.json()] == [1001]
    assert client.get("/api/cases?priority=urgent").status_code == 422


def test_empty_database_returns_empty_list(tmp_path):
    database_path = tmp_path / "empty.sqlite3"
    with TestClient(create_app(database_path)) as client:
        client.headers["X-Demo-User-Id"] = "1"
        with connect(database_path) as connection, connection:
            connection.execute("DELETE FROM cases")
        assert client.get("/api/cases").json() == []


def test_restart_does_not_duplicate_seed_and_foreign_keys_are_enforced(tmp_path):
    database_path = tmp_path / "integrity.sqlite3"
    initialize_database(database_path)
    initialize_database(database_path)
    with connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 4
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO cases (title, summary, owner_agency_id, priority) VALUES (?, ?, ?, ?)",
                ("Invalid agency", "Synthetic test", 999, "low"),
            )
