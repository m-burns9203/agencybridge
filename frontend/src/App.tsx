// File: App.tsx
// Description: Coordinates demo identity, case creation, inbox, and SQL reporting.
// Author: Michael Burns <mdburnsjr@gmail.com>
// Created: 2026-10-08
// Last Modified: 2026-10-08 by Michael Burns
// Dependencies: react, api.ts, useApi.ts, CaseForm.tsx, CaseDetails.tsx

import { useState } from "react";
import type {
  Agency,
  CaseRecord,
  DemoUser,
  Priority,
  Referral,
  ReportRow,
} from "./api";
import { useApi } from "./useApi";
import CaseForm from "./CaseForm";
import CaseDetails from "./CaseDetails";

type View = "cases" | "inbox" | "report";

export default function App() {
  const users = useApi<DemoUser[]>("/demo-users");
  const agencies = useApi<Agency[]>("/agencies");
  const [userId, setUserId] = useState(1);
  const user = users.data?.find((person) => person.id === userId);

  if (users.loading || agencies.loading)
    return (
      <main className="startup" role="status">
        Loading your workspace…
      </main>
    );
  if (users.error || agencies.error || !user || !agencies.data)
    return (
      <main className="startup">
        <h1>Workspace unavailable</h1>
        <p role="alert">
          {users.error || agencies.error || "No demo user found."}
        </p>
        <button
          onClick={() => {
            users.reload();
            agencies.reload();
          }}
        >
          Try again
        </button>
      </main>
    );

  // A new identity gets a fresh component. This clears the previous user's case
  // selection, cached results, drafts, and messages instead of carrying them over.
  return (
    <Workspace
      key={user.id}
      user={user}
      users={users.data!}
      agencies={agencies.data}
      onUserChange={setUserId}
    />
  );
}

function Workspace({
  user,
  users,
  agencies,
  onUserChange,
}: {
  user: DemoUser;
  users: DemoUser[];
  agencies: Agency[];
  onUserChange: (id: number) => void;
}) {
  const [view, setView] = useState<View>("cases");
  const [priority, setPriority] = useState<"all" | Priority>("all");
  const [revision, setRevision] = useState(0);
  const [selectedCase, setSelectedCase] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [lookup, setLookup] = useState("");
  const cases = useApi<CaseRecord[]>(
    `/cases${priority === "all" ? "" : `?priority=${priority}`}`,
    user.id,
    revision,
  );
  const inbox = useApi<Referral[]>("/referrals/inbox", user.id, revision);
  const report = useApi<ReportRow[]>("/analytics/referrals", user.id, revision);

  function refresh() {
    setRevision((value) => value + 1);
  }
  function navigate(next: View) {
    setView(next);
    setSelectedCase(null);
    setCreating(false);
  }
  function openCase(id: number) {
    setSelectedCase(id);
    setCreating(false);
  }
  const active = view === "cases" ? cases : view === "inbox" ? inbox : report;

  return (
    <div className="workspace">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="AgencyBridge home">
          <span className="brand-mark">ab</span>AgencyBridge
        </a>
        <p className="sidebar-caption">COORDINATION WORKSPACE</p>
        <nav aria-label="Workspace">
          <button
            className={view === "cases" ? "nav-active" : "nav-button"}
            aria-current={view === "cases" ? "page" : undefined}
            onClick={() => navigate("cases")}
          >
            Cases <span>01</span>
          </button>
          <button
            className={view === "inbox" ? "nav-active" : "nav-button"}
            aria-current={view === "inbox" ? "page" : undefined}
            onClick={() => navigate("inbox")}
          >
            Referral inbox <span>02</span>
          </button>
          <button
            className={view === "report" ? "nav-active" : "nav-button"}
            aria-current={view === "report" ? "page" : undefined}
            onClick={() => navigate("report")}
          >
            Referral report <span>03</span>
          </button>
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" /> Local prototype
          <p>
            Clear ownership.
            <br />
            Explicit sharing.
            <br />
            Traceable changes.
          </p>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            Workspace / <strong>{user.agency_name}</strong>
          </span>
          <span className="demo-tag">FICTIONAL DATA</span>
        </header>
        <div className="identity-bar">
          <label>
            Demo user
            <select
              value={user.id}
              onChange={(event) => onUserChange(Number(event.target.value))}
            >
              {users.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name} · {person.agency_name}
                </option>
              ))}
            </select>
          </label>
          <button onClick={refresh}>Refresh workspace</button>
        </div>
        <div className="scope-note">
          <strong>Demo identity</strong>
          <span>
            Switch fictional users to explore agency permissions. This selector
            simulates identity; it is not a secure login. Switching users clears
            unsaved forms.
          </span>
        </div>
        {selectedCase !== null ? (
          <CaseDetails
            key={selectedCase}
            caseId={selectedCase}
            user={user}
            agencies={agencies}
            revision={revision}
            onChanged={refresh}
            onBack={() => setSelectedCase(null)}
          />
        ) : (
          <>
            <section className="page-heading">
              <p className="eyebrow">AGENCYBRIDGE / COORDINATION IN PRACTICE</p>
              <h1>
                {view === "cases"
                  ? "The right information.\nThe right agency."
                  : view === "inbox"
                    ? "Your next connection."
                    : "A clearer view of referrals."}
              </h1>
              <p className="intro">
                {view === "cases"
                  ? "Cases owned by your agency or explicitly shared with it."
                  : view === "inbox"
                    ? "Review incoming referrals and open a case to accept or complete it."
                    : "Pending referrals sent by your agency, grouped by receiving agency."}
              </p>
            </section>
            {creating && (
              <CaseForm
                user={user}
                onCancel={() => setCreating(false)}
                onCreated={(record) => {
                  setCreating(false);
                  setPriority("all");
                  setSelectedCase(record.id);
                  refresh();
                }}
              />
            )}
            <section
              className="case-section"
              aria-labelledby="workspace-heading"
            >
              <div className="list-toolbar">
                <div>
                  <h2 id="workspace-heading">
                    {view === "cases"
                      ? "Your case directory"
                      : view === "inbox"
                        ? "Incoming referrals"
                        : "Pending referrals sent"}
                  </h2>
                  <p>{user.agency_name}</p>
                </div>
                {view === "cases" && (
                  <div className="actions">
                    <label>
                      Filter priority
                      <select
                        value={priority}
                        onChange={(event) =>
                          setPriority(event.target.value as "all" | Priority)
                        }
                      >
                        <option value="all">All priorities</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                      </select>
                    </label>
                    <button
                      className="primary"
                      onClick={() => setCreating(true)}
                    >
                      New case
                    </button>
                  </div>
                )}
              </div>
              <div aria-live="polite" aria-busy={active.loading}>
                {active.loading ? (
                  <p className="message">Loading…</p>
                ) : active.error ? (
                  <div className="message error" role="alert">
                    {active.error}{" "}
                    <button onClick={active.reload}>Try again</button>
                  </div>
                ) : (
                  <>
                    {view === "cases" &&
                      (cases.data?.length === 0 ? (
                        <p className="message">
                          No accessible cases match this priority.
                        </p>
                      ) : (
                        <div className="case-grid">
                          {cases.data?.map((record) => (
                            <article className="case-card" key={record.id}>
                              <div className="card-top">
                                <span className="case-id">
                                  CASE-{record.id}
                                </span>
                                <span className={`priority ${record.priority}`}>
                                  {record.priority} priority
                                </span>
                              </div>
                              <h3>{record.title}</h3>
                              <p className="summary">{record.summary}</p>
                              <div className="card-bottom">
                                <span>
                                  {record.agency_name}
                                  <br />
                                  <small>
                                    {record.owner_agency_id === user.agency_id
                                      ? "Owned by your agency"
                                      : "Shared by referral"}
                                  </small>
                                </span>
                                <button
                                  aria-label={`Open case ${record.id}`}
                                  onClick={() => openCase(record.id)}
                                >
                                  Open case →
                                </button>
                              </div>
                            </article>
                          ))}
                        </div>
                      ))}
                    {view === "inbox" &&
                      (inbox.data?.length === 0 ? (
                        <p className="message">
                          No incoming referrals yet. Send one from another
                          agency to see it here.
                        </p>
                      ) : (
                        <div className="case-grid">
                          {inbox.data?.map((referral) => (
                            <article className="case-card" key={referral.id}>
                              <div className="card-top">
                                <span className="case-id">
                                  CASE-{referral.case_id}
                                </span>
                                <span className={`status ${referral.status}`}>
                                  {referral.status}
                                </span>
                              </div>
                              <h3>{referral.case_title}</h3>
                              <p>From {referral.from_agency_name}</p>
                              <button
                                onClick={() => openCase(referral.case_id)}
                              >
                                Review referral
                              </button>
                            </article>
                          ))}
                        </div>
                      ))}
                    {view === "report" && (
                      <div className="panel">
                        <table>
                          <caption>
                            Pending referrals from {user.agency_name}
                          </caption>
                          <thead>
                            <tr>
                              <th scope="col">Receiving agency</th>
                              <th scope="col">Pending referrals</th>
                            </tr>
                          </thead>
                          <tbody>
                            {report.data?.map((row) => (
                              <tr key={row.agency_id}>
                                <th scope="row">{row.agency_name}</th>
                                <td>{row.pending_referrals}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <p className="muted">
                          Includes agencies with zero pending referrals.
                          Accepted and completed referrals are excluded.
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
              {view === "cases" && (
                <form
                  className="lookup-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const id = Number(lookup);
                    if (Number.isSafeInteger(id) && id > 0) openCase(id);
                  }}
                >
                  <label>
                    Open case by ID
                    <input
                      type="number"
                      min="1"
                      step="1"
                      required
                      placeholder="1001"
                      value={lookup}
                      onChange={(event) => setLookup(event.target.value)}
                    />
                  </label>
                  <button type="submit">Look up case</button>
                  <p>
                    Knowing an ID does not grant access. Try a case owned by
                    another agency.
                  </p>
                </form>
              )}
            </section>
          </>
        )}
        <footer>
          AgencyBridge{" "}
          <span>Independent portfolio prototype · Synthetic records only</span>
        </footer>
      </main>
    </div>
  );
}
