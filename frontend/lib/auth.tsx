"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, clearCache, get, post, setUnauthorizedHandler } from "./api";

export type Me = { id: number; name: string; name_en: string; phone: string; balance: number; points: number; demo: boolean };
type State = { status: "loading" | "in" | "out" | "error"; me?: Me };
type Ctx = State & { refresh: () => Promise<void>; logout: () => Promise<void>; setName: (n: string) => void };
const AuthCtx = createContext<Ctx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<State>({ status: "loading" });
  const refresh = useCallback(async () => {
    try { setS({ status: "in", me: await get<Me>("/me") }); }
    catch (e) { setS({ status: e instanceof ApiError && e.status === 401 ? "out" : "error" }); }
  }, []);
  useEffect(() => {
    setUnauthorizedHandler(() => { clearCache(); setS({ status: "out" }); }); // any 401 anywhere returns the user to sign-in
    void refresh();
  }, [refresh]);
  const logout = useCallback(async () => {
    try { await post("/auth/logout"); } finally { clearCache(); setS({ status: "out" }); }
  }, []);
  const setName = (name: string) => setS((p) => (p.me ? { ...p, me: { ...p.me, name, name_en: name } } : p));
  return <AuthCtx.Provider value={{ ...s, refresh, logout, setName }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
