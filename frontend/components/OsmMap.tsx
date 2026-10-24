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

  useEffect(() => {
    const leaflet = L.current;
    if (!ready || !leaflet || !map.current) return;
    markers.current.forEach((mk) => mk.remove());
    markers.current = orgs.map((o) => {
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
        html: `<span class="${cls}" style="transform:translate(-50%,-100%);display:inline-flex">${ICON[o.kind] ?? "🏢"} ${o.available_now}/${o.items}</span>`,
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
    });
  }, [orgs, ready, selectedId]);

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
