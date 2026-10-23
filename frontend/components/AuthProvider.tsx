"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthState = {
  user: User | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api<{ user: User }>("/auth/me", { noRedirect: true });
      setUser(data.user);
    } catch (e) {
      setUser(null);
      if (!(e instanceof ApiError && e.status === 401)) setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST", noRedirect: true });
    } finally {
      setUser(null);
      // 로그아웃 후 화면 상태를 모두 비우기 위해 전체 새로고침
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  return <AuthContext.Provider value={{ user, loading, error, refresh, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider 안에서 사용해야 합니다.");
  return ctx;
}

/** 로그인된 사용자 (AppShell 안에서는 항상 존재) */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("로그인 사용자 없음");
  return user;
}
