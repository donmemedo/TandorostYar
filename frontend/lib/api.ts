"use client";
import { useCallback, useEffect, useState } from "react";

export type PactType = "gym" | "steps" | "nutrition";
export type Pact = { id: number; type: PactType; target_days: number; stake: number; goal: number; today: number; done_days: number; days: string[]; at_risk: number };
export type Pool = { amount: number; fee: number; charity: number; fee_rate: number; participants: number; on_track: number; pacts: number };
export type Dash = { user: { name: string; name_en: string; balance: number; points: number; streak: number }; pacts: Pact[]; pool: Pool; week: string[]; today: string };

export function useApi<T>(path: string) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState(false);
  const reload = useCallback(
    () => fetch("/api" + path).then((r) => (r.ok ? r.json() : Promise.reject())).then((d) => { setData(d); setError(false); }, () => setError(true)),
    [path],
  );
  useEffect(() => { reload(); }, [reload]);
  return { data, error, reload, setData };
}

/** POST and return JSON; throws Error(detail) where detail is a backend error code like "exists". */
export async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch("/api" + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body ?? {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "generic");
  return j;
}
