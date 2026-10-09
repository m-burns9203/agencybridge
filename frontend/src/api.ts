// File: api.ts
// Description: Defines API types and sends requests using a selected demo identity.
// Author: Michael Burns <mdburnsjr@gmail.com>
// Created: 2026-10-08
// Last Modified: 2026-10-08 by Michael Burns
// Dependencies: Browser Fetch API

export type Priority = "low" | "medium" | "high";
export type ReferralStatus = "pending" | "accepted" | "completed";
export interface Agency {
  id: number;
  name: string;
}
export interface DemoUser {
  id: number;
  name: string;
  agency_id: number;
  agency_name: string;
}
export interface CaseRecord {
  id: number;
  title: string;
  summary: string;
  owner_agency_id: number;
  agency_name: string;
  priority: Priority;
  created_at: string;
}
export interface Referral {
  id: number;
  case_id: number;
  to_agency_id: number;
  agency_name: string;
  case_title: string;
  from_agency_name: string;
  status: ReferralStatus;
  created_at: string;
}
export interface AuditEvent {
  id: number;
  actor_name: string;
  agency_name: string;
  action: string;
  created_at: string;
}
export interface CaseDetail extends CaseRecord {
  referrals: Referral[];
  events: AuditEvent[];
}
export interface ReportRow {
  agency_id: number;
  agency_name: string;
  pending_referrals: number;
}
export interface CaseInput {
  title: string;
  summary: string;
  priority: Priority;
}

export async function api<T>(
  path: string,
  userId?: number,
  options: RequestInit = {},
): Promise<T> {
  // This caller-controlled header simulates identity. It is deliberately NOT a
  // password or token; the interface labels the limitation prominently.
  const headers = new Headers(options.headers);
  if (userId !== undefined) headers.set("X-Demo-User-Id", String(userId));
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    // FastAPI uses a string for our business errors and an array for validation
    // errors. Translate both into a readable message, including the bad field.
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map(
                (item: { loc: string[]; msg: string }) =>
                  `${item.loc.slice(1).join(".")}: ${item.msg}`,
              )
              .join("; ")
          : `Request failed (${response.status}). Check that the Python server is running.`;
    throw new Error(message);
  }
  // This type assertion aids development; the backend response models validate
  // the JSON. TypeScript does not itself inspect network data at runtime.
  return response.json() as Promise<T>;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}

export function formatTime(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}
