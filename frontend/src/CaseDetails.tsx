// File: CaseDetails.tsx
// Description: Displays a case, owner actions, referrals, and shared activity history.
// Author: Michael Burns <mdburnsjr@gmail.com>
// Created: 2026-10-08
// Last Modified: 2026-10-08 by Michael Burns
// Dependencies: react, api.ts, useApi.ts

import { useState } from "react";
import { api, errorMessage, formatTime } from "./api";
import type { Agency, CaseDetail, DemoUser, Priority } from "./api";
import { useApi } from "./useApi";

export default function CaseDetails({
  caseId,
  user,
  agencies,
  revision,
  onChanged,
  onBack,
}: {
  caseId: number;
  user: DemoUser;
  agencies: Agency[];
  revision: number;
  onChanged: () => void;
  onBack: () => void;
}) {
  const result = useApi<CaseDetail>(`/cases/${caseId}`, user.id, revision);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function mutate(
    path: string,
    method: string,
    body: object,
    message: string,
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, user.id, { method, body: JSON.stringify(body) });
      setNotice(message);
      onChanged(); // Reload case, inbox, and report from the database after success.
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  const record = result.data;
  return (
    <section className="case-section">
      <button className="back-button" onClick={onBack}>
        ← Back to workspace
      </button>
      {notice && (
        <p className="success" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}
      {result.loading ? (
        <p role="status">Loading case…</p>
      ) : result.error ? (
        <div className="message error" role="alert">
          {result.error} <button onClick={result.reload}>Try again</button>
        </div>
      ) : (
        record && (
          <>
            <div className="panel">
              <div className="card-top">
                <span className="case-id">CASE-{record.id}</span>
                <span className={`priority ${record.priority}`}>
                  {record.priority} priority
                </span>
              </div>
              <h2 className="detail-title">{record.title}</h2>
              <p className="case-summary">{record.summary}</p>
              <p className="muted">
                Owned by {record.agency_name} · Created{" "}
                {formatTime(record.created_at)} UTC
              </p>
              {/* Hiding owner controls improves usability. The API repeats the check;
            someone crafting their own HTTP request must still be rejected. */}
              {record.owner_agency_id === user.agency_id ? (
                <div className="owner-actions">
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const form = new FormData(event.currentTarget);
                      void mutate(
                        `/cases/${caseId}`,
                        "PATCH",
                        { priority: form.get("priority") as Priority },
                        "Priority saved.",
                      );
                    }}
                  >
                    <fieldset disabled={busy}>
                      <label>
                        Update priority
                        <select name="priority" defaultValue={record.priority}>
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                        </select>
                      </label>
                      <button type="submit">Save priority</button>
                    </fieldset>
                  </form>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const form = new FormData(event.currentTarget);
                      void mutate(
                        `/cases/${caseId}/referrals`,
                        "POST",
                        { to_agency_id: Number(form.get("agency")) },
                        "Referral sent. The receiving agency can now view this case.",
                      );
                    }}
                  >
                    <fieldset disabled={busy}>
                      <label>
                        Refer to agency
                        <select name="agency" required defaultValue="">
                          <option value="" disabled>
                            Choose an agency
                          </option>
                          {agencies
                            .filter(
                              (agency) =>
                                agency.id !== record.owner_agency_id &&
                                !record.referrals.some(
                                  (referral) =>
                                    referral.to_agency_id === agency.id,
                                ),
                            )
                            .map((agency) => (
                              <option key={agency.id} value={agency.id}>
                                {agency.name}
                              </option>
                            ))}
                        </select>
                      </label>
                      <button type="submit" className="primary">
                        Send referral
                      </button>
                    </fieldset>
                  </form>
                </div>
              ) : (
                <p className="scope-note">
                  Shared with your agency by referral. Only the owner can edit
                  or share this case.
                </p>
              )}
            </div>
            <div className="detail-columns">
              <section className="panel">
                <h2>Referrals</h2>
                <p className="muted">Pending → Accepted → Completed</p>
                {record.referrals.length === 0 ? (
                  <p>No referrals yet.</p>
                ) : (
                  record.referrals.map((referral) => (
                    <div className="referral-row" key={referral.id}>
                      <strong>{referral.agency_name}</strong>
                      <span className={`status ${referral.status}`}>
                        {referral.status}
                      </span>
                      {referral.to_agency_id === user.agency_id &&
                        referral.status !== "completed" && (
                          <button
                            disabled={busy}
                            onClick={() =>
                              void mutate(
                                `/referrals/${referral.id}`,
                                "PATCH",
                                {
                                  status:
                                    referral.status === "pending"
                                      ? "accepted"
                                      : "completed",
                                },
                                "Referral status updated.",
                              )
                            }
                          >
                            {referral.status === "pending"
                              ? "Accept referral"
                              : "Complete referral"}
                          </button>
                        )}
                    </div>
                  ))
                )}
              </section>
              <section className="panel">
                <h2>Activity timeline</h2>
                <p className="muted">
                  Successful changes · Most recent first · UTC
                </p>
                {record.events.length === 0 ? (
                  <p>This seeded case has no recorded changes yet.</p>
                ) : (
                  <ol className="timeline">
                    {record.events.map((event) => (
                      <li key={event.id}>
                        <strong>{event.action}</strong>
                        <span>
                          {event.actor_name} · {event.agency_name}
                        </span>
                        <time dateTime={event.created_at}>
                          {formatTime(event.created_at)}
                        </time>
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            </div>
          </>
        )
      )}
    </section>
  );
}
