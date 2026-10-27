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

// 새로고침·QR 로 들어올 때 '로그인 확인' 을 기다리지 않도록 마지막 사용자 정보를 이 탭에만 기억한다.
// 화면 표시용일 뿐이고 권한은 서버가 매 요청 확인한다. 뒤에서 바로 다시 확인해 바뀌면 고친다.
const USER_KEY = "pgm.me";

function readCachedUser(): User | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function writeCachedUser(user: User | null) {
  try {
    if (user) sessionStorage.setItem(USER_KEY, JSON.stringify(user));
    else sessionStorage.removeItem(USER_KEY);
  } catch {
    /* 저장소를 못 쓰는 브라우저는 그냥 매번 확인 */
  }
}

/** 로그인·로그아웃 때 이전 사용자 정보를 지운다 */
export function clearCachedUser() {
  writeCachedUser(null);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (background = false) => {
    if (!background) setLoading(true);
    setError(null);
    try {
      const data = await api<{ user: User }>("/auth/me", { noRedirect: true });
      setUser(data.user);
      writeCachedUser(data.user);
    } catch (e) {
      const unauth = e instanceof ApiError && e.status === 401;
      if (unauth || !background) setUser(null);
      if (unauth) writeCachedUser(null);
      else if (!background) setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST", noRedirect: true });
    } finally {
      setUser(null);
      writeCachedUser(null);
      // 로그아웃 후 화면 상태를 모두 비우기 위해 전체 새로고침
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    }
  }, []);

  useEffect(() => {
    const cached = readCachedUser();
    if (cached) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUser(cached);
      setLoading(false);
    }
    refresh(Boolean(cached));
  }, [refresh]);

  // 이미 로그인 화면이 떠 있으면 화면을 지우지 않고 뒤에서 다시 확인한다 (내 정보 저장 후 등)
  const hasUser = user !== null;
  const refreshNow = useCallback(() => refresh(hasUser), [refresh, hasUser]);

  return <AuthContext.Provider value={{ user, loading, error, refresh: refreshNow, logout }}>{children}</AuthContext.Provider>;
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
