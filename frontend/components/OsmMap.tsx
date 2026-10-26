"use client";

import "leaflet/dist/leaflet.css";
import type { Map as LeafletMap, Marker } from "leaflet";
import { useEffect, useRef, useState } from "react";
import type { MapOrg } from "@/lib/types";
import type { Bounds } from "./KakaoMap";

const ICON: Record<string, string> = {
  school: "🏫",
  community_center: "🏛",
  other: "🏢",
};

function escapeHtml(s: string) {
  return s.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
}

type Group = {
  lat: number;
  lng: number;
  total: number;
  school: number;
  center: number;
  other: number;
  bounds: [[number, number], [number, number]];
};

const CELL_PX = 70; // 화면에서 이 거리 안의 기관은 하나로 묶음
const NO_CLUSTER_ZOOM = 16; // 이만큼 확대하면 묶지 않고 하나씩

/** 화면 격자로 가까운 기관을 묶는다. 선택된 기관과 혼자 있는 기관은 그대로 보여 준다. */
function clusterOrgs(orgs: MapOrg[], m: LeafletMap, selectedId: number | null) {
  if (m.getZoom() >= NO_CLUSTER_ZOOM) return { singles: orgs, groups: [] as Group[] };
  const cells = new Map<string, MapOrg[]>();
  const singles: MapOrg[] = [];
  for (const o of orgs) {
    if (o.id === selectedId) {
      singles.push(o);
      continue;
    }
    const p = m.project([o.lat, o.lng], m.getZoom());
    const key = `${Math.floor(p.x / CELL_PX)}:${Math.floor(p.y / CELL_PX)}`;
    const list = cells.get(key);
    if (list) list.push(o);
    else cells.set(key, [o]);
  }
  const groups: Group[] = [];
  for (const list of cells.values()) {
    if (list.length === 1) {
      singles.push(list[0]);
      continue;
    }
    const lats = list.map((o) => o.lat);
    const lngs = list.map((o) => o.lng);
    groups.push({
      lat: lats.reduce((a, b) => a + b, 0) / list.length,
      lng: lngs.reduce((a, b) => a + b, 0) / list.length,
      total: list.length,
      school: list.filter((o) => o.kind === "school").length,
      center: list.filter((o) => o.kind === "community_center").length,
      other: list.filter((o) => o.kind === "other").length,
      bounds: [
        [Math.min(...lats), Math.min(...lngs)],
        [Math.max(...lats), Math.max(...lngs)],
      ],
    });
  }
  return { singles, groups };
}

/** 키가 필요 없는 지도 (OpenStreetMap). KakaoMap 과 같은 사용법. */
export default function OsmMap({
  orgs,
  selectedId,
  onSelect,
  onBounds,
  focus,
}: {
  orgs: MapOrg[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onBounds: (b: Bounds) => void;
  focus: { lat: number; lng: number; level?: number; key: number } | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const L = useRef<typeof import("leaflet") | null>(null);
  const [ready, setReady] = useState(false);
  const cb = useRef({ onSelect, onBounds });
  useEffect(() => {
    cb.current = { onSelect, onBounds };
  });

  useEffect(() => {
    let alive = true;
    let m: LeafletMap | null = null;
    import("leaflet").then((leaflet) => {
      if (!alive || !box.current) return;
      L.current = leaflet;
      m = leaflet
        .map(box.current, { zoomControl: true })
        .setView([37.5665, 126.978], 12);
      leaflet
        .tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 기여자',
        })
        .addTo(m);
      const emit = () => {
        const b = m!.getBounds();
        const r = (n: number) => Math.round(n * 1e4) / 1e4;
        cb.current.onBounds({
          sw_lat: r(b.getSouth()),
          sw_lng: r(b.getWest()),
          ne_lat: r(b.getNorth()),
          ne_lng: r(b.getEast()),
        });
      };
      m.on("moveend", emit);
      map.current = m;
      setReady(true);
      emit();
    });
    return () => {
      alive = false;
      m?.remove();
      map.current = null;
    };
  }, []);

  // 지도를 움직이거나 확대·축소하면 묶음을 다시 계산
  const [view, setView] = useState(0);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const bump = () => setView((v) => v + 1);
    m.on("zoomend moveend", bump);
    return () => {
      m.off("zoomend moveend", bump);
    };
  }, [ready]);

  useEffect(() => {
    const leaflet = L.current;
    const m = map.current;
    if (!ready || !leaflet || !m) return;
    markers.current.forEach((mk) => mk.remove());
    const { singles, groups } = clusterOrgs(orgs, m, selectedId);
    const groupMarkers = groups.map((g) => {
      const parts = [
        g.school ? `🏫 ${g.school}` : "",
        g.center ? `🏛 ${g.center}` : "",
        g.other ? `🏢 ${g.other}` : "",
      ].filter(Boolean);
      const size = g.total >= 100 ? 15 : 13;
      const icon = leaflet.divIcon({
        className: "",
        html: `<span style="transform:translate(-50%,-50%);display:inline-flex;align-items:center;gap:6px;white-space:nowrap;border-radius:9999px;border:2px solid #fff;background:#0f766e;color:#fff;font-weight:700;font-size:${size}px;padding:4px 11px;box-shadow:0 2px 8px rgb(13 27 51 / .4)">${parts.join(" · ")}</span>`,
        iconSize: [0, 0],
      });
      const label = `이 근처 학교 ${g.school}곳, 주민센터 ${g.center}곳${g.other ? `, 기타 ${g.other}곳` : ""}. 눌러서 확대`;
      const mk = leaflet.marker([g.lat, g.lng], { icon, title: label, alt: label, keyboard: true }).addTo(m);
      mk.on("click", () => m.fitBounds(g.bounds, { padding: [40, 40], maxZoom: 17 }));
      mk.getElement()?.setAttribute("aria-label", label);
      return mk;
    });
    markers.current = [...groupMarkers, ...singles.map((o) => {
      const available = o.available_now > 0;
      const selected = o.id === selectedId;
      const cls = [
        "flex items-center gap-1 rounded-full border-2 px-2 py-0.5 text-xs font-bold shadow-md whitespace-nowrap",
        selected
          ? "border-navy-900 bg-navy-900 text-white"
          : available
            ? "border-teal-700 bg-white text-teal-900"
            : "border-slate-400 bg-white text-slate-600",
      ].join(" ");
      const icon = leaflet.divIcon({
        className: "",
        // 지도 배경에 묻히지 않게 조금 크게 + 아래 꼬리로 정확한 위치를 가리킴
        html: `<span class="${cls}" style="transform:translate(-50%,calc(-100% - 7px));display:inline-flex;font-size:13px;padding:3px 10px;box-shadow:0 2px 6px rgb(13 27 51 / .35)">${ICON[o.kind] ?? "🏢"} ${o.available_now}/${o.items}</span><span style="position:absolute;left:-6px;top:-9px;width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:9px solid ${selected ? "#0d1b33" : available ? "#0f766e" : "#94a3b8"}"></span>`,
        iconSize: [0, 0],
      });
      const mk = leaflet
        .marker([o.lat, o.lng], {
          icon,
          title: o.name,
          alt: `${o.name}, 지금 빌릴 수 있는 물품 ${o.available_now}개`,
          keyboard: true,
          zIndexOffset: selected ? 1000 : 0,
        })
        .addTo(map.current!);
      mk.on("click", () => cb.current.onSelect(o.id));
      mk.getElement()?.setAttribute(
        "aria-label",
        `${escapeHtml(o.name)}, 지금 빌릴 수 있는 물품 ${o.available_now}개`,
      );
      return mk;
    })];
  }, [orgs, ready, selectedId, view]);

  useEffect(() => {
    if (!ready || !focus || !map.current) return;
    map.current.setView(
      [focus.lat, focus.lng],
      focus.level ? 15 : map.current.getZoom(),
    );
  }, [focus, ready]);

  return (
    <div
      ref={box}
      className="h-full w-full"
      role="application"
      aria-label="기관 위치 지도"
    />
  );
}
