# Understanding the referral workflow

Documentation date: October 8, 2026.

The project now demonstrates one complete workflow: an agency creates a case,
refers it, and another agency accepts and completes the referral. A third agency
cannot read it by guessing its ID. Each successful change creates an activity
entry in the same database transaction.

## 1. The five tables

```text
agencies ──< users
    │
    └──────< cases ──< referrals >── agencies (recipient)
                 │
                 └──< audit_events >── users (actor)
```

The notation `──<` means one record can be related to many records.

- An **agency** is the organization used by the permission rules.
- A **user** identifies an individual action and belongs to an agency.
- A **case** contains the shared summary and has one permanent owner.
- A **referral** connects a case to a recipient and tracks that agency's work.
- An **audit event** records who changed a case or referral and when.

Why separate cases and referrals? Two receiving agencies can be at different
stages on the same case. A single case status would be ambiguous. Each referral
therefore owns its pending/accepted/completed status.

Why not store a sending agency on a referral? The sender is always the case owner,
and ownership never changes here. Storing both could allow contradictory values.
If transfers were supported, we would revisit this and preserve the original sender.

`UNIQUE(case_id, to_agency_id)` prevents two referrals for the same pair. The UI
also removes already-referred agencies from its dropdown. The constraint remains
necessary because users can bypass the UI and requests can arrive concurrently.

## 2. Identity is different from permission

| ID | Fictional user | Agency |
|---|---|---|
| 1 | Alex Morgan | Community Services |
| 2 | Jordan Lee | Public Safety |
| 3 | Sam Rivera | School Support |

The browser sends the selection in `X-Demo-User-Id`. The `current_user()` function
looks up the user's agency in SQLite. Missing or unknown identities return HTTP
401. `Depends(current_user)` tells FastAPI to run this lookup before the route
and supply its result as the route's user argument.

This does **not authenticate a person**. Anyone can select any demo user. Its role
is to simulate identities while exercising authorization. A real application
would need a verified session or token and would still need the access checks below.

Case creation derives ownership from this user. It does not accept ownership from
the request body. `extra="forbid"` in `models.py` rejects unexpected fields, so
adding `owner_agency_id: 2` to a creation request returns a validation error.

`str_strip_whitespace=True` trims text before checking its length. That stops a
title consisting of spaces from passing the minimum-length check. `Field` limits
the title and summary lengths, and Literal types limit priority and status values.

## 3. The permission rule in SQL

A case is visible when the user's agency owns it or has received a referral:

```sql
c.owner_agency_id = ?
OR EXISTS (
    SELECT 1 FROM referrals r
    WHERE r.case_id = c.id AND r.to_agency_id = ?
)
```

Both placeholders bind the user's agency ID. `EXISTS` asks whether a matching row
exists. Unlike joining all matching referrals directly, it cannot duplicate a case.

The case list applies this condition before returning data. Detail and history
endpoints call `visible_case()` with the same rule. Hiding a card or button in React
would not protect a record from direct HTTP requests.

Sharing begins when a referral is sent, allowing the recipient to read it before
accepting. Completing a referral retains access to its history. This is an explicit
prototype policy, not a claim about real agency policy.

| Action | Owner | Recipient | Unrelated agency |
|---|---|---|---|
| Read case and timeline | Yes | Yes | No |
| Edit priority | Yes | No | No |
| Refer onward | Yes | No | No |
| Advance a recipient's referral | No | That recipient only | No |

`require_owner()` separates read permission from edit/share permission. Recipients
attempting those writes receive HTTP 403. Missing and inaccessible case IDs both
receive HTTP 404 so the API does not confirm another agency's record exists.

All authorized readers see the full summary, referrals, and timeline. There are no
field-level restrictions. No recipient can re-share the case from this interface
or through the API; only its owner can add recipients.

## 4. Follow a referral through the backend

1. The owner submits `POST /api/cases/{id}/referrals` with `to_agency_id`.
2. FastAPI resolves the demo user and validates the body.
3. The route opens a connection and reserves a write transaction.
4. It checks case visibility, then ownership.
5. It rejects self-referrals and unknown agencies.
6. It inserts the pending referral. Duplicate pairs return HTTP 409.
7. It inserts an activity event using the same connection.
8. The transaction commits and the response returns HTTP 201.

`with connect(path) as connection, connection:` uses two context managers. Our
custom one closes the connection. SQLite's own context commits on success or
rolls back when an exception escapes the block.

`BEGIN IMMEDIATE` reserves SQLite's writer before reading mutable state. That
serializes these small read-check-write operations. It is not optimistic locking:
two successive priority edits still use last-write-wins. It is also not a queue
for coordinating external systems.

`record_event()` must not independently commit. A referral and its history entry
belong to one transaction. If either insert fails, neither should remain saved.
The same rule applies to case creation, priority changes, and referral updates.

## 5. Controlled status transitions

The allowed changes form a small state machine:

```python
next_status = {"pending": "accepted", "accepted": "completed"}
```

Pending can become accepted; accepted can become completed. Completed has no next
state. Skipping or reversing returns HTTP 409 because the operation conflicts with
the current record state.

Repeating the current status is a no-op: return the record without another event.
This helps when the server saved a change but its response was lost and the client
retried. Only the recipient can make even this no-op request.

Duplicate referral creation instead returns 409. The unique pair constraint is
duplicate prevention, not a general idempotency-key implementation. Case creation
has no idempotency key; retrying after an ambiguous failure could create a second
case. That is a useful future improvement to discuss honestly.

## 6. The report and LEFT JOIN

The report counts pending referrals sent by the selected agency's owned cases.
It does not expose other owners' referral totals.

```sql
SELECT a.id AS agency_id,
       a.name AS agency_name,
       COUNT(r.id) AS pending_referrals
FROM agencies a
LEFT JOIN referrals r ON r.to_agency_id = a.id
    AND r.status = 'pending'
    AND r.case_id IN (
        SELECT id FROM cases WHERE owner_agency_id = ?
    )
GROUP BY a.id, a.name
ORDER BY a.id;
```

`LEFT JOIN` retains agencies with no qualifying referrals. Their referral fields
are NULL. `COUNT(r.id)` ignores those NULLs and gives zero; `COUNT(*)` would wrongly
count the retained agency row as one.

The status condition belongs in `ON` here. Moving it to `WHERE r.status = 'pending'`
would discard unmatched NULL rows and lose zero-count agencies. The ownership
subquery also restricts the match without discarding the agency row itself.

## 7. The frontend, one responsibility at a time

**api.ts** defines shared response types and sends requests with the identity
header. It checks `response.ok`: fetch does not automatically reject HTTP errors.
FastAPI business errors use a string while validation errors use an array; the
helper translates both into readable messages.

The generic parameter in `api<CaseRecord>()` tells TypeScript what the response
should look like. It does not inspect JSON at runtime. The Python response models
validate the server's response contract.

**useApi.ts** extracts the repeated read-only fetch pattern into a custom hook.
A custom hook is a reusable function that calls React hooks. Its name starts with
`use`; call it at the top level of a component or another hook, not conditionally.

Its request key includes path, user ID, refresh revision, and retry counter. A
result appears only when it matches the current key. This avoids showing stale
data during a filter change. An AbortController cancels superseded requests and
prevents them from changing state later.

**App.tsx** loads fictional users/agencies and renders Workspace. The user's ID
is the Workspace component's `key`. Changing it unmounts the previous workspace
and creates a fresh one, clearing old selections, responses, and unsaved drafts.
No global state or routing library is necessary for these three simple views.

**CaseForm.tsx** stores a draft in controlled inputs. React state holds each value,
and onChange updates it. Browser required/length checks help the user; backend
validation still protects direct callers. Failed submissions retain the draft and
show an error. The form is disabled while submitting to discourage double clicks.

**CaseDetails.tsx** displays one case and its actions. Its small action forms use
native fields and `FormData` at submit time, avoiding extra state variables for
one-field actions. They are recreated with current server values when the detail
reloads after success.

After a mutation succeeds, `onChanged()` increases a revision counter. The case,
inbox, and report hooks refetch. This keeps the database as the source of truth
instead of manually patching several cached arrays. A larger app might use a
query-cache library, but this is easier to follow at the current scale.

The UI shows controls appropriate to the current agency. That improves usability;
the backend independently enforces every rule. Switching users mid-request does
not change the identity already attached to that request.

## 8. Tests and their limits

Tests use temporary SQLite files rather than the demo database. The suite covers
identity requirements, validation, derived ownership, cross-agency reads/writes,
duplicate referrals, invalid transitions, harmless repeats, retained access after
completion, and report isolation including zero-count agencies.

The rollback tests install a temporary database trigger that rejects audit inserts.
They run the real route and inspect the database afterward. Case creation, priority
editing, referral creation, and acceptance must all roll back. This proves the
transaction boundary rather than just asserting that a mocked helper was called.

The suite does not prove demo identity is secure. It intentionally is not. History
is append-only through the API, but a database owner can edit the file. Events log
successful changes, not reads or denials. The labels for actors/agencies are joined
from their current records; historical snapshots would matter if renaming or agency
transfers were added. Those operations do not exist in this prototype.

## 9. Interview rehearsal

Create a case as Alex, refer it, show the report, switch to Jordan to accept and
complete, then switch to Sam and look up the ID. Return to Alex to show history.

Practice answering these aloud:

1. Why derive agency ownership from the user rather than accepting it in the body?
2. Why are a case and a referral separate records?
3. What if the same request is submitted twice?
4. What if the history write fails after the referral insert?
5. Why is the case still visible after referral completion?
6. Why use COUNT(r.id), and why is the status condition in ON?
7. What would need to change for production?

Reasonable next steps include verified authentication, pagination, conflict
detection, explicit revocation, creation idempotency, durable audit storage, and
external-system adapters. These are discussion points, not implemented features.
First, make sure you can explain the current flow without reading this guide.
