# First milestone: database to browser

Documentation date: October 8, 2026.

**Historical guide:** this describes the initial read-only milestone. Read
[the coordination walkthrough](coordination-walkthrough.md) for the current
implementation, which adds demo identities, permissions, writes, referrals,
and history. The case list now returns only cases accessible to the chosen agency.

## What you have built

There are three moving parts:

```text
React browser page
    | GET /api/cases?priority=high
    v
Vite development proxy → FastAPI route
                            | SELECT ... JOIN ... WHERE ...
                            v
                       SQLite database file
                            |
React state ← JSON array ← Python dictionaries
```

React decides what the user sees. Python decides what data the endpoint returns.
SQLite stores the records. Vite serves the frontend during development and forwards
requests whose paths start with `/api` to Python.

The filter is deliberately implemented on the server: it gives you practice
connecting a form control to a query parameter and then to a SQL WHERE clause.
For four records, filtering in React would also be reasonable. Server filtering
becomes useful when fetching every record would be expensive.

## 1. The schema: relationships before endpoints

Open `backend/schema.sql`.

An agency has an ID and a name. A case has its own ID and an `owner_agency_id`.
The owner field is a **foreign key**: it refers to an existing agency's primary
key. One agency can own many cases, while each case has one owning agency.

Why not repeat the agency name in every case? A name change would require editing
many rows. Keeping the name in the agencies table gives it one authoritative home.

`NOT NULL` means a value is required. `UNIQUE` prevents two identical agency names.
`CHECK` constrains priority to low, medium, or high. These rules protect the data
even if a future script writes directly to SQLite without going through FastAPI.

The `created_at` default supplies a UTC timestamp for inserts that omit it. Seed
records explicitly supply October 8 timestamps for this demonstration. Text is
adequate here because timestamps use the same sortable UTC format.

Interview question: **What happens if a case references agency 999?** The insert
fails with a foreign-key error. SQLite only enforces that rule when we enable
`PRAGMA foreign_keys = ON` on the connection, which our helper does every time.

## 2. Opening and closing the database

Open `backend/database.py`.

`Path(__file__).resolve().parent` finds the directory containing this file. This
keeps the database location stable even when a command starts elsewhere.

`connect()` is a context manager. Code can write `with connect(path) as connection`
and be sure the connection closes afterward. `yield` hands the connection to the
caller; `finally` performs cleanup whether the caller succeeds or raises an error.

The `row_factory` setting lets us access columns by name. Named columns are easier
to understand and less fragile than remembering that position 4 means priority.

There are two distinct responsibilities:

- Our custom `connect()` context closes the connection.
- SQLite's `with connection:` context commits a transaction on success or rolls it
  back on failure.

We use both when seeding data. A transaction groups writes so they succeed or fail
together. Later, the same pattern will keep a referral and its audit event together.

`executemany()` runs the same statement with multiple sets of values. The `?`
placeholders represent bound parameters: SQLite receives values separately from
the SQL statement. Never construct SQL by inserting user text into a query string.

`ON CONFLICT(id) DO NOTHING` makes repeated startup inserts harmless for existing
seed IDs. It does not silently ignore other constraint violations. This is a small
seed routine, not a database migration system.

## 3. Turning an HTTP request into a SQL query

Open `backend/main.py`.

`create_app()` returns a configured FastAPI application. Taking the database path
as an argument gives tests an easy way to use disposable data without changing
the production code or touching the demo database.

The lifespan function initializes the database before serving requests. The module's
last line creates the app object that Uvicorn imports. Uvicorn is the process that
listens for HTTP requests; FastAPI defines how those requests are handled.

The decorator `@app.get('/api/cases', ...)` connects a GET request at that path to
the function underneath it. GET reads data. Future POST endpoints will create data.

`priority: Priority | None = None` means the priority parameter is optional.
`Priority` is a Literal type with three permitted strings. FastAPI validates the
incoming query parameter using this annotation. `?priority=urgent` returns HTTP
422 because that value is outside the contract.

The query starts with:

```sql
SELECT c.id, c.title, a.name AS agency_name
FROM cases AS c
JOIN agencies AS a ON a.id = c.owner_agency_id
```

`c` and `a` are short aliases for the tables. `JOIN` pairs each case with its owning
agency. `AS agency_name` gives the returned column a clear name for the API.
An inner JOIN is appropriate because each case must have an existing owner.

If a priority was supplied, we add a fixed `WHERE c.priority = ?` clause and bind
the value separately. We add only SQL text we control, never raw user input.
`ORDER BY` returns the newest cases first, with ID breaking any timestamp ties.

`fetchall()` reads the matching rows. `[dict(row) for row in rows]` is a Python list
comprehension: convert each row into a dictionary and collect those dictionaries.
FastAPI validates the result against `CaseResponse` and serializes it as JSON.

Why use regular `def` rather than `async def` for the endpoint? The built-in sqlite3
driver performs blocking I/O. FastAPI runs synchronous route functions in its
thread pool; labeling blocking database work async would not make it nonblocking.

The current endpoint returns all fictional cases. It does **not** enforce agency
access. Later, that access condition belongs in the backend query, alongside any
filter, before records leave the server.

## 4. Rendering the response in React

Open `frontend/src/App.tsx`.

`CaseRecord` describes one returned object. TypeScript uses the interface to catch
mistakes while editing or building: accessing `record.agencyName` would be wrong
because the API field is `agency_name`. This type annotation does not inspect JSON
at runtime. We currently rely on the Python response model for that contract.

Each `useState` call stores a value between renders and returns a setter:

- `cases` stores the response array.
- `priority` stores the user's selected filter.
- `loading` indicates a request in progress.
- `error` holds a failure message, or null when there is no failure.
- `retryCount` lets the retry button trigger the request again.

Calling a setter asks React to render again with the updated value. Do not mutate
the existing cases array directly; give React a new value through `setCases`.

The select is a **controlled input**: its value comes from React state, and its
change handler updates that state. There is one source of truth for the selection.

`useEffect` synchronizes the component with the API. Its dependency array contains
priority and retryCount, so it runs initially and after either changes. The inner
async function uses `await` to wait for the response without blocking the browser.
The effect itself returns cleanup rather than a Promise.

`fetch` can resolve successfully even when the server returns HTTP 500. That is why
we check `response.ok` before reading the response as successful data. The catch
branch displays an error, and the finally branch clears the loading state.

The AbortController addresses a subtle race: choose High and immediately choose
Low. If the High response arrives last, it must not replace Low's results. Cleanup
aborts the old request, and the state updates also check whether it was aborted.
React StrictMode exercises setup and cleanup an extra time in development; that
can produce a canceled initial request in the browser's network panel.

The JSX displays exactly one request state: loading, error, empty, or results.
`cases.map(...)` creates a card for every record. `key={record.id}` gives React a
stable identity for each card when the array changes.

We display dates in UTC explicitly so these demo dates do not shift depending on
the browser's local timezone. A production product would choose an appropriate
user-facing timezone intentionally.

## 5. Why the frontend can reach Python

Open `frontend/vite.config.ts`.

The browser requests `/api/cases` from the same origin that served the page,
normally port 5173. Vite sees `/api` and forwards the request to port 8000. Python
handles it and the response returns through Vite.

This avoids hardcoding a backend URL in the React component. The proxy is only a
development feature. A deployed app would need an explicitly configured route
to the backend, or a separate API origin with appropriate CORS settings.

## 6. What the tests prove

Open `backend/test_cases.py`.

The client fixture creates a real temporary SQLite database and runs the FastAPI
app against it. A fixture supplies reusable setup for tests. The TestClient context
also runs startup, so these tests include the initialization behavior.

The checks cover the case/agency JOIN, ordering, valid filtering, rejection of an
invalid priority, an empty result, startup without duplicates, and foreign-key
enforcement. They do not prove authorization, because authorization is not built.
The frontend build checks types and bundling; it does not replace browser testing.

## Practice explaining it aloud

Try answering these without reading the files first:

1. What happens after you choose High in the dropdown?
2. Why is agency_name absent from the cases table but present in the API response?
3. Why use a question-mark parameter instead of formatting the priority into SQL?
4. What is the difference between closing a connection and committing a transaction?
5. Why does TypeScript's CaseRecord interface not validate JSON at runtime?
6. What could go wrong if an old request were allowed to overwrite newer results?
7. Where should agency permissions go when we introduce users?

A useful first exercise: add a second high-priority fictional seed case with a new
ID, restart Python, and predict how the list and filter will change. Then trace
the new record through SQL, Python dictionaries, JSON, React state, and its card.
