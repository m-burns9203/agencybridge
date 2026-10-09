# File: main.py
# Description: Handles case ownership, cross-agency referrals, and activity history.
# Author: Michael Burns <mdburnsjr@gmail.com>
# Created: 2026-10-08
# Last Modified: 2026-10-08 by Michael Burns
# Dependencies: fastapi, contextlib, pathlib, sqlite3, backend.database, backend.models

from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3

from fastapi import Depends, FastAPI, Header, HTTPException

from backend.database import DEFAULT_DATABASE_PATH, connect, initialize_database
from backend.models import (
    AgencyResponse, AuditResponse, CaseDetail, CaseEdit, CaseInput, CaseResponse,
    Priority, ReferralInput, ReferralResponse, ReferralUpdate, ReportRow, UserResponse,
)

# Fixed SQL fragments, never user input. EXISTS checks a relationship without
# duplicating a case that has several referrals.
CASE_SELECT = """
    SELECT c.*, a.name AS agency_name FROM cases c
    JOIN agencies a ON a.id = c.owner_agency_id
"""
VISIBLE_CASE = """
    (c.owner_agency_id = ? OR EXISTS (
        SELECT 1 FROM referrals r WHERE r.case_id = c.id AND r.to_agency_id = ?
    ))
"""
REFERRAL_SELECT = """
    SELECT r.*, recipient.name AS agency_name, c.title AS case_title,
           owner.name AS from_agency_name
    FROM referrals r
    JOIN cases c ON c.id = r.case_id
    JOIN agencies recipient ON recipient.id = r.to_agency_id
    JOIN agencies owner ON owner.id = c.owner_agency_id
"""


def visible_case(connection, case_id: int, user: UserResponse):
    """Return a case only if this agency owns it or received a referral."""
    case = connection.execute(
        CASE_SELECT + " WHERE c.id = ? AND " + VISIBLE_CASE,
        (case_id, user.agency_id, user.agency_id),
    ).fetchone()
    # Match the missing-record answer to avoid revealing another agency's IDs.
    if case is None:
        raise HTTPException(404, "Case not found or unavailable to your agency.")
    return case


def require_owner(case, user: UserResponse) -> None:
    """Read permission does not imply permission to edit or share a case."""
    if case["owner_agency_id"] != user.agency_id:
        raise HTTPException(403, "Only the owning agency can change or refer this case.")


def record_event(connection, case_id: int, user: UserResponse, action: str) -> None:
    """Share the caller's transaction; do not independently commit an event."""
    connection.execute(
        "INSERT INTO audit_events (case_id, actor_user_id, action) VALUES (?, ?, ?)",
        (case_id, user.id, action),
    )


def case_events(connection, case_id: int):
    """Read history after the caller has checked access to the case."""
    return [dict(row) for row in connection.execute(
        """SELECT e.id, e.action, e.created_at, u.name AS actor_name,
                  a.name AS agency_name
           FROM audit_events e JOIN users u ON u.id = e.actor_user_id
           JOIN agencies a ON a.id = u.agency_id
           WHERE e.case_id = ? ORDER BY e.id DESC""", (case_id,),
    )]


def create_app(database_path: Path = DEFAULT_DATABASE_PATH) -> FastAPI:
    """Construct an app with a replaceable database path for isolated tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database(database_path)
        yield

    app = FastAPI(title="AgencyBridge", version="0.2.0", lifespan=lifespan)

    def current_user(x_demo_user_id: int | None = Header(default=None)) -> UserResponse:
        """Resolve a DEMO identity, not a verified login or authentication token.

        Anyone using this local demo can choose any seeded user. The server
        derives agency membership from its database, not a client agency field.
        Production would require replacing this header with verified identity.
        """
        with connect(database_path) as connection:
            row = connection.execute(
                """SELECT u.*, a.name AS agency_name FROM users u
                   JOIN agencies a ON a.id = u.agency_id WHERE u.id = ?""",
                (x_demo_user_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(401, "Choose a valid demo user.")
        return UserResponse(**dict(row))

    # These public directories contain only fictional demonstration identities.
    @app.get("/api/demo-users", response_model=list[UserResponse])
    def demo_users():
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute(
                """SELECT u.*, a.name AS agency_name FROM users u
                   JOIN agencies a ON a.id = u.agency_id ORDER BY u.id""",
            )]

    @app.get("/api/agencies", response_model=list[AgencyResponse])
    def agencies():
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM agencies ORDER BY id")]

    @app.get("/api/cases", response_model=list[CaseResponse])
    def list_cases(priority: Priority | None = None, user: UserResponse = Depends(current_user)):
        query = CASE_SELECT + " WHERE " + VISIBLE_CASE
        parameters = [user.agency_id, user.agency_id]
        if priority is not None:
            query += " AND c.priority = ?"
            parameters.append(priority)
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute(
                query + " ORDER BY c.created_at DESC, c.id DESC", parameters,
            )]

    @app.post("/api/cases", response_model=CaseResponse, status_code=201)
    def create_case(body: CaseInput, user: UserResponse = Depends(current_user)):
        with connect(database_path) as connection, connection:
            cursor = connection.execute(
                """INSERT INTO cases (title, summary, priority, owner_agency_id)
                   VALUES (?, ?, ?, ?)""",
                (body.title, body.summary, body.priority, user.agency_id),
            )
            case_id = cursor.lastrowid
            record_event(connection, case_id, user, "Created case")
            return dict(visible_case(connection, case_id, user))

    @app.get("/api/cases/{case_id}", response_model=CaseDetail)
    def get_case(case_id: int, user: UserResponse = Depends(current_user)):
        with connect(database_path) as connection:
            case = dict(visible_case(connection, case_id, user))
            case["referrals"] = [dict(row) for row in connection.execute(
                REFERRAL_SELECT + " WHERE r.case_id = ? ORDER BY r.id DESC", (case_id,),
            )]
            case["events"] = case_events(connection, case_id)
            return case

    @app.patch("/api/cases/{case_id}", response_model=CaseResponse)
    def edit_case(case_id: int, body: CaseEdit, user: UserResponse = Depends(current_user)):
        with connect(database_path) as connection, connection:
            # Reserve the write before reading state. This serializes these small
            # SQLite writes; it does not provide optimistic conflict detection.
            connection.execute("BEGIN IMMEDIATE")
            case = visible_case(connection, case_id, user)
            require_owner(case, user)
            if case["priority"] != body.priority:
                connection.execute("UPDATE cases SET priority = ? WHERE id = ?", (body.priority, case_id))
                record_event(connection, case_id, user, f"Changed priority from {case['priority']} to {body.priority}")
            return dict(visible_case(connection, case_id, user))

    @app.post("/api/cases/{case_id}/referrals", response_model=ReferralResponse, status_code=201)
    def create_referral(case_id: int, body: ReferralInput, user: UserResponse = Depends(current_user)):
        with connect(database_path) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            require_owner(visible_case(connection, case_id, user), user)
            if body.to_agency_id == user.agency_id:
                raise HTTPException(422, "Choose an agency other than the case owner.")
            recipient = connection.execute("SELECT * FROM agencies WHERE id = ?", (body.to_agency_id,)).fetchone()
            if recipient is None:
                raise HTTPException(422, "Receiving agency does not exist.")
            try:
                cursor = connection.execute(
                    "INSERT INTO referrals (case_id, to_agency_id) VALUES (?, ?)",
                    (case_id, body.to_agency_id),
                )
            except sqlite3.IntegrityError:
                # UNIQUE also guards against concurrent duplicate requests.
                raise HTTPException(409, "This case has already been referred to that agency.") from None
            record_event(connection, case_id, user, f"Referred case to {recipient['name']}")
            return dict(connection.execute(REFERRAL_SELECT + " WHERE r.id = ?", (cursor.lastrowid,)).fetchone())

    @app.get("/api/referrals/inbox", response_model=list[ReferralResponse])
    def inbox(user: UserResponse = Depends(current_user)):
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute(
                REFERRAL_SELECT + " WHERE r.to_agency_id = ? ORDER BY r.id DESC", (user.agency_id,),
            )]

    @app.patch("/api/referrals/{referral_id}", response_model=ReferralResponse)
    def update_referral(referral_id: int, body: ReferralUpdate, user: UserResponse = Depends(current_user)):
        with connect(database_path) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            referral = connection.execute(
                REFERRAL_SELECT + " WHERE r.id = ? AND r.to_agency_id = ?", (referral_id, user.agency_id),
            ).fetchone()
            if referral is None:
                raise HTTPException(404, "Referral not found or unavailable to your agency.")
            # Repeating the current status is a no-op, useful when a successful
            # response was lost. It also avoids a duplicate audit event.
            if body.status != referral["status"]:
                next_status = {"pending": "accepted", "accepted": "completed"}
                if next_status.get(referral["status"]) != body.status:
                    raise HTTPException(409, "Referrals must move pending → accepted → completed.")
                connection.execute("UPDATE referrals SET status = ? WHERE id = ?", (body.status, referral_id))
                record_event(connection, referral["case_id"], user, f"{body.status.capitalize()} referral for {referral['agency_name']}")
            return dict(connection.execute(REFERRAL_SELECT + " WHERE r.id = ?", (referral_id,)).fetchone())

    @app.get("/api/cases/{case_id}/audit-events", response_model=list[AuditResponse])
    def audit_events(case_id: int, user: UserResponse = Depends(current_user)):
        with connect(database_path) as connection:
            visible_case(connection, case_id, user)
            return case_events(connection, case_id)

    @app.get("/api/analytics/referrals", response_model=list[ReportRow])
    def referral_report(user: UserResponse = Depends(current_user)):
        """Count only pending referrals sent from cases owned by this agency."""
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute(
                """SELECT a.id AS agency_id, a.name AS agency_name,
                          COUNT(r.id) AS pending_referrals
                   FROM agencies a
                   LEFT JOIN referrals r ON r.to_agency_id = a.id
                     AND r.status = 'pending'
                     AND r.case_id IN (SELECT id FROM cases WHERE owner_agency_id = ?)
                   GROUP BY a.id, a.name ORDER BY a.id""", (user.agency_id,),
            )]

    return app


app = create_app()
