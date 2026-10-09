-- File: schema.sql
-- Description: Defines agencies, users, cases, referrals, and activity history.
-- Author: Michael Burns <mdburnsjr@gmail.com>
-- Created: 2026-10-08
-- Last Modified: 2026-10-08 by Michael Burns
-- Dependencies: SQLite

CREATE TABLE IF NOT EXISTS agencies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    -- Store the agency ID once; JOIN to agencies when we need its name.
    owner_agency_id INTEGER NOT NULL REFERENCES agencies(id),
    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
    -- SQLite stores this UTC timestamp as text, which is sufficient here.
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    agency_id INTEGER NOT NULL REFERENCES agencies(id)
);

CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    to_agency_id INTEGER NOT NULL REFERENCES agencies(id),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'completed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    -- One referral per case/recipient, even after completion. A repeated click
    -- cannot create duplicates; re-referral is deliberately outside this demo.
    UNIQUE (case_id, to_agency_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    actor_user_id INTEGER NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Indexes support the relationships used by permission checks and the inbox.
CREATE INDEX IF NOT EXISTS cases_owner_idx ON cases(owner_agency_id);
CREATE INDEX IF NOT EXISTS referrals_recipient_idx ON referrals(to_agency_id, status);
CREATE INDEX IF NOT EXISTS audit_case_idx ON audit_events(case_id, id);
