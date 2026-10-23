"use client";

/* eslint-disable @typescript-eslint/no-explicit-any -- 카카오 지도 SDK 는 타입 정의를 제공하지 않음 */
import { useEffect, useRef, useState } from "react";
import type { MapOrg } from "@/lib/types";

export const KAKAO_KEY = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY ?? "";

export type Bounds = { sw_lat: number; sw_lng: number; ne_lat: number; ne_lng: number };

declare global {
  interface Window {
    kakao?: any;
  }
}

let loader: Promise<any> | null = null;

function loadKakao(): Promise<any> {
  if (loader) return loader;
  loader = new Promise((resolve, reject) => {
    if (window.kakao?.maps) {
      window.kakao.maps.load(() => resolve(window.kakao));
      return;
    }
    const s = document.createElement("script");
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(KAKAO_KEY)}&autoload=false`;
    s.async = true;
    s.onload = () => {
      if (!window.kakao?.maps) return reject(new Error("카카오 지도 SDK를 불러오지 못했습니다."));
      window.kakao.maps.load(() => resolve(window.kakao));
    };
    s.onerror = () => {
      loader = null;
      reject(new Error("카카오 지도를 불러오지 못했습니다. 지도 키와 등록된 사이트 도메인을 확인해 주세요."));
    };
    document.head.appendChild(s);
  });
  return loader;
}

const ICON: Record<string, string> = { school: "🏫", community_center: "🏛", other: "🏢" };

export default function KakaoMap({
  orgs,
  selectedId,
  onSelect,
  onBounds,
  focus,
  onError,
}: {
  orgs: MapOrg[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onBounds: (b: Bounds) => void;
  /** 이 좌표로 지도 이동 (내 위치 등) */
  focus: { lat: number; lng: number; level?: number; key: number } | null;
  onError: (msg: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<any>(null);
  const overlays = useRef<any[]>([]);
  const [ready, setReady] = useState(false);
  const cb = useRef({ onSelect, onBounds, onError });
  useEffect(() => {
    cb.current = { onSelect, onBounds, onError };
  });

  useEffect(() => {
    let alive = true;
    loadKakao()
      .then((kakao) => {
        if (!alive || !box.current) return;
        const m = new kakao.maps.Map(box.current, { center: new kakao.maps.LatLng(37.5665, 126.978), level: 6 });
        m.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
        const emit = () => {
          const b = m.getBounds();
          const r = (n: number) => Math.round(n * 1e4) / 1e4;
          cb.current.onBounds({
            sw_lat: r(b.getSouthWest().getLat()),
            sw_lng: r(b.getSouthWest().getLng()),
            ne_lat: r(b.getNorthEast().getLat()),
            ne_lng: r(b.getNorthEast().getLng()),
          });
        };
        kakao.maps.event.addListener(m, "idle", emit);
        map.current = m;
        setReady(true);
        emit();
      })
      .catch((e: Error) => cb.current.onError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  // 기관 표시 (데이터가 바뀌면 다시 그림)
  useEffect(() => {
    const kakao = window.kakao;
    if (!ready || !kakao || !map.current) return;
    overlays.current.forEach((o) => o.setMap(null));
    overlays.current = orgs.map((o) => {
      const el = document.createElement("button");
      el.type = "button";
      const available = o.available_now > 0;
      const selected = o.id === selectedId;
      el.className = [
        "flex items-center gap-1 rounded-full border-2 px-2 py-0.5 text-xs font-bold shadow-md whitespace-nowrap",
        selected ? "border-navy-900 bg-navy-900 text-white" : available ? "border-teal-700 bg-white text-teal-900" : "border-slate-400 bg-white text-slate-600",
      ].join(" ");
      el.setAttribute("aria-label", `${o.name}, 지금 빌릴 수 있는 물품 ${o.available_now}개`);
      el.textContent = `${ICON[o.kind] ?? "🏢"} ${o.available_now}/${o.items}`;
      el.title = o.name;
      el.addEventListener("click", () => cb.current.onSelect(o.id));
      const ov = new kakao.maps.CustomOverlay({
        position: new kakao.maps.LatLng(o.lat, o.lng),
        content: el,
        yAnchor: 1,
        zIndex: selected ? 10 : 1,
      });
      ov.setMap(map.current);
      return ov;
    });
  }, [orgs, ready, selectedId]);

  useEffect(() => {
    const kakao = window.kakao;
    if (!ready || !focus || !kakao) return;
    map.current.setCenter(new kakao.maps.LatLng(focus.lat, focus.lng));
    if (focus.level) map.current.setLevel(focus.level);
  }, [focus, ready]);

  return <div ref={box} className="h-full w-full" role="application" aria-label="기관 위치 지도" />;
}
