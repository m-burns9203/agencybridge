// File: CaseForm.tsx
// Description: Collects and submits a new fictional case with accessible feedback.
// Author: Michael Burns <mdburnsjr@gmail.com>
// Created: 2026-10-08
// Last Modified: 2026-10-08 by Michael Burns
// Dependencies: react, api.ts

import { useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "./api";
import type { CaseRecord, DemoUser, Priority } from "./api";

export default function CaseForm({
  user,
  onCreated,
  onCancel,
}: {
  user: DemoUser;
  onCreated: (record: CaseRecord) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); // Keep the browser from navigating away on submit.
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const record = await api<CaseRecord>("/cases", user.id, {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          summary: summary.trim(),
          priority,
        }),
      });
      onCreated(record);
    } catch (failure) {
      // Keep the draft in place so a validation or network error loses no work.
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="create-heading">
      <h2 id="create-heading">Create a case</h2>
      <p>
        Owned by <strong>{user.agency_name}</strong>. Use fictional information
        only.
      </p>
      <form onSubmit={(event) => void submit(event)}>
        <fieldset disabled={busy}>
          <label>
            Case title
            <input
              autoFocus
              required
              minLength={3}
              maxLength={120}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label>
            Summary
            <textarea
              required
              minLength={10}
              maxLength={2000}
              rows={4}
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
            />
          </label>
          <label>
            Case priority
            <select
              value={priority}
              onChange={(event) => setPriority(event.target.value as Priority)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          <div className="actions">
            <button className="primary" type="submit">
              {busy ? "Creating…" : "Create case"}
            </button>
            <button type="button" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </fieldset>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
