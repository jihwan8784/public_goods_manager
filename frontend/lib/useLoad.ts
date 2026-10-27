"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";
import { cacheGet, cacheSet } from "./loadCache";

type Options = {
  /** 이 간격(ms)마다 화면을 자동으로 새로 불러온다. 탭이 보이지 않을 때는 멈춘다. */
  refreshMs?: number;
};

/** GET 요청 + 로딩/오류/다시 불러오기 + (선택) 자동 갱신.
 * 이미 본 화면으로 돌아오면 기억해 둔 결과를 바로 보여 주고 뒤에서 새로 받는다. */
export function useLoad<T>(path: string | null, opts: Options = {}) {
  const hit = path ? cacheGet(path) : undefined;
  const [data, setData] = useState<T | null>((hit?.data as T) ?? null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!hit);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const seq = useRef(0);
  const lastJson = useRef<string>(hit?.json ?? "");

  const load = useCallback(
    async (background: boolean) => {
      if (!path) return;
      const my = ++seq.current;
      if (!background) {
        setLoading(true);
        setError(null);
      }
      try {
        const res = await api<T>(path);
        if (my !== seq.current) return; // 더 최근 요청이 있으면 무시
        // 결과가 이전과 같으면 화면을 다시 그리지 않는다 (지도·긴 목록의 버벅임 방지)
        const json = JSON.stringify(res);
        cacheSet(path, res, json);
        if (json !== lastJson.current) {
          lastJson.current = json;
          setData(res);
        }
        setError(null);
        setUpdatedAt(new Date());
      } catch (e) {
        if (my !== seq.current) return;
        // 자동 갱신 실패는 기존 화면을 유지하고 오류만 표시하지 않는다
        if (!background) setError(errorMessage(e));
      } finally {
        if (my === seq.current && !background) setLoading(false);
      }
    },
    [path],
  );

  const reload = useCallback(() => load(false), [load]);

  useEffect(() => {
    // 주소가 바뀌었을 때 기억해 둔 결과가 있으면 먼저 보여 주고 뒤에서 새로 받는다
    const cached = path ? cacheGet(path) : undefined;
    if (cached && cached.json !== lastJson.current) {
      lastJson.current = cached.json;
      setData(cached.data as T);
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(Boolean(cached));
  }, [load, path]);

  useEffect(() => {
    if (!opts.refreshMs || !path) return;
    const tick = () => {
      if (document.visibilityState === "visible") load(true);
    };
    const id = window.setInterval(tick, opts.refreshMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [opts.refreshMs, path, load]);

  return { data, error, loading, reload, updatedAt };
}
