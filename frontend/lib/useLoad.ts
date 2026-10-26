"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";

type Options = {
  /** 이 간격(ms)마다 화면을 자동으로 새로 불러온다. 탭이 보이지 않을 때는 멈춘다. */
  refreshMs?: number;
};

/** GET 요청 + 로딩/오류/다시 불러오기 + (선택) 자동 갱신 */
export function useLoad<T>(path: string | null, opts: Options = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const seq = useRef(0);
  const lastJson = useRef<string>("");

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
        // 자동 갱신 결과가 이전과 같으면 화면을 다시 그리지 않는다 (지도·긴 목록의 버벅임 방지)
        const json = JSON.stringify(res);
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
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(false);
  }, [load]);

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
