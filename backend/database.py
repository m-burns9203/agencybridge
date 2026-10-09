# File: database.py
# Description: Opens SQLite connections and seeds fictional demonstration cases.
# Author: Michael Burns <mdburnsjr@gmail.com>
# Created: 2026-10-08
# Last Modified: 2026-10-08 by Michael Burns
# Dependencies: sqlite3, contextlib, pathlib (Python standard library)

import sqlite3
from contextlib import contextmanager
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = BACKEND_DIR / "agencybridge.sqlite3"


@contextmanager
def connect(database_path: Path):
    """Yield one connection, then close it even if the calling code fails."""
    connection = sqlite3.connect(database_path)
    # Rows become accessible by column name instead of positions like row[0].
    connection.row_factory = sqlite3.Row
    # SQLite requires foreign-key checking to be enabled on every connection.
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    """Create missing tables and insert demo records without duplicating them."""
    with connect(database_path) as connection:
        connection.executescript((BACKEND_DIR / "schema.sql").read_text())
        # This inner context commits both seed operations together, or rolls
        # them back if either fails. Closing a connection alone does not commit.
        with connection:
            connection.executemany(
                "INSERT INTO agencies (id, name) VALUES (?, ?) ON CONFLICT(id) DO NOTHING",
                [(1, "Community Services"), (2, "Public Safety"), (3, "School Support")],
            )
            connection.executemany(
                "INSERT INTO users (id, name, agency_id) VALUES (?, ?, ?) ON CONFLICT(id) DO NOTHING",
                [(1, "Alex Morgan", 1), (2, "Jordan Lee", 2), (3, "Sam Rivera", 3)],
            )
            # Bound parameters keep values separate from executable SQL.
            # Fixed IDs make restarting the server safe for this seed routine.
            connection.executemany(
                """
                INSERT INTO cases
                    (id, title, summary, owner_agency_id, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                [
                    (1001, "Family resource coordination", "Fictional household requesting help connecting with community resources.", 1, "high", "2026-10-08T14:00:00Z"),
                    (1002, "Community outreach follow-up", "Fictional neighborhood outreach request awaiting coordination.", 2, "medium", "2026-10-08T15:00:00Z"),
                    (1003, "Student support coordination", "Fictional request to coordinate school and community support.", 3, "low", "2026-10-08T16:00:00Z"),
                    (1004, "Transportation assistance", "Fictional request for transportation to a community appointment.", 1, "medium", "2026-10-08T17:00:00Z"),
                ],
            )
