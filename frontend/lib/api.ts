"use client";
import { useCallback, useEffect, useState } from "react";

export type PactType = "gym" | "steps" | "nutrition";
export type Pact = { id: number; type: PactType; target_days: number; stake: number; goal: number; today: number; done_days: number; days: string[]; at_risk: number; ends: string | null };
export type Pool = { amount: number; fee: number; charity: number; fee_rate: number; participants: number; on_track: number; pacts: number };
export type Dash = { user: { name: string; name_en: string; balance: number; points: number; streak: number }; pacts: Pact[]; pool: Pool; week: string[]; today: string; days_left: number; demo: boolean; paused: boolean };

/** A backend error code such as "exists" or "rate_limited"; "network" when the server could not be reached. */
export class ApiError extends Error {
  constructor(public code: string, public status: number) { super(code); }
}

let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (f: () => void) => { onUnauthorized = f; };

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch("/api" + path, {
      method, credentials: "same-origin",
      headers: method === "GET" ? undefined : { "content-type": "application/json" }, // required by the server's CSRF rule
      body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
    });
  } catch { throw new ApiError("network", 0); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && path !== "/me") onUnauthorized();
    throw new ApiError(typeof j.detail === "string" ? j.detail : r.status >= 500 ? "server" : "generic", r.status);
  }
  return j;
}

// Tiny stale-while-revalidate cache: a page you have seen paints instantly from memory, then refreshes.
type Entry = { data?: unknown; inflight?: Promise<unknown> };
const cache = new Map<string, Entry>();
export const clearCache = () => cache.clear();

export const get = <T,>(path: string) => request<T>("GET", path);
async function write<T>(method: string, path: string, body?: unknown): Promise<T> {
  const out = await request<T>(method, path, body);
  cache.clear(); // any write may change what other pages show
  return out;
}
export const post = <T,>(path: string, body?: unknown) => write<T>("POST", path, body);
export const patch = <T,>(path: string, body?: unknown) => write<T>("PATCH", path, body);
export const del = <T,>(path: string) => write<T>("DELETE", path);

export function useApi<T>(path: string) {
  const [, tick] = useState(0);
  const [error, setError] = useState(false);
  const data = cache.get(path)?.data as T | undefined;
  const reload = useCallback(async () => {
    const e = cache.get(path) ?? {};
    cache.set(path, e);
    e.inflight ??= request<T>("GET", path).then((d) => { e.data = d; return d; }).finally(() => { e.inflight = undefined; });
    try { await e.inflight; setError(false); } catch { setError(true); }
    tick((n) => n + 1);
  }, [path]);
  useEffect(() => { void reload(); }, [reload]);
  const setData = (d: T) => { cache.set(path, { data: d }); tick((n) => n + 1); };
  return { data, error: error && !data, reload, setData };
}
