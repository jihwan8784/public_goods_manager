"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useUser } from "@/components/AuthProvider";
import KakaoMap, { KAKAO_KEY, type Bounds } from "@/components/KakaoMap";
import OsmMap from "@/components/OsmMap";
import {
  btn,
  Empty,
  ErrorState,
  inputBase,
  LiveBadge,
  Loading,
  PageHeader,
} from "@/components/ui";
import { api } from "@/lib/api";
import { ORG_KIND_ICON, ORG_KIND_LABEL } from "@/lib/labels";
import type { MapOrg, OrgBrief, OrgKind } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type SearchHit = OrgBrief & { address: string };

/** 기관 이름·주소로 찾아서 지도에서 그 위치로 이동 */
function MapSearch({ kind, onPick }: { kind: "" | OrgKind; onPick: (h: SearchHit) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");

  async function search(e: React.FormEvent) {
    e.preventDefault();
    const term = q.trim();
    if (term.length < 2) {
      setHits(null);
      setState("error");
      return;
    }
    setState("loading");
    try {
      const params = new URLSearchParams({ q: term, limit: "20" });
      if (kind) params.set("kind", kind);
      const r = await api<{ orgs: SearchHit[] }>(`/orgs/search?${params}`);
      setHits(r.orgs);
      setState("idle");
    } catch {
      setHits(null);
      setState("error");
    }
  }

  return (
    <div className="mb-3">
      <form role="search" onSubmit={search} className="flex gap-2">
        <label className="sr-only" htmlFor="map-search">
          기관 이름이나 주소로 찾기
        </label>
        <input
          id="map-search"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="학교·주민센터 이름이나 주소로 찾기 (예: 가온고, 서교동)"
          className={`${inputBase} min-w-0 flex-1`}
        />
        <button type="submit" className={btn.primary} disabled={state === "loading"}>
          {state === "loading" ? "찾는 중…" : "검색"}
        </button>
      </form>
      <div aria-live="polite">
        {state === "error" && (
          <p className="mt-1 text-sm font-semibold text-rose-800">
            {q.trim().length < 2 ? "2글자 이상 입력해 주세요." : "검색하지 못했습니다. 잠시 후 다시 시도해 주세요."}
          </p>
        )}
        {hits && hits.length === 0 && <p className="mt-1 text-sm text-navy-600">검색 결과가 없습니다.</p>}
        {hits && hits.length > 0 && (
          <ul className="mt-2 max-h-64 overflow-y-auto rounded-lg border border-navy-100 bg-white shadow-sm">
            {hits.map((h) => (
              <li key={h.id}>
                <button
                  type="button"
                  onClick={() => {
                    onPick(h);
                    setHits(null);
                  }}
                  className="block w-full border-b border-navy-50 px-3 py-2 text-left text-sm hover:bg-navy-50 focus:bg-navy-50"
                >
                  <span aria-hidden>{ORG_KIND_ICON[h.kind]} </span>
                  <span className="font-semibold">{h.name}</span>
                  {h.lat == null && <span className="ml-1 text-xs text-amber-800">(위치 미등록)</span>}
                  <span className="block text-xs text-navy-600">{h.address || h.region}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function OrgMap() {
  const user = useUser();
  // 카카오 키가 있으면 카카오맵, 없거나 불러오지 못하면 키가 필요 없는 OpenStreetMap
  const [engine, setEngine] = useState<"kakao" | "osm">(
    KAKAO_KEY ? "kakao" : "osm",
  );
  const [mapError, setMapError] = useState("");
  const [bounds, setBounds] = useState<Bounds | null>(null);
  const [kind, setKind] = useState<"" | OrgKind>("");
  const [withItems, setWithItems] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  // 학교 인증한 학생은 자기 학교 주변에서 시작
  const school = user.student.school;
  const [focus, setFocus] = useState<{
    lat: number;
    lng: number;
    level?: number;
    key: number;
  } | null>(
    school?.lat && school?.lng
      ? { lat: school.lat, lng: school.lng, level: 5, key: 0 }
      : null,
  );
  const [geoMsg, setGeoMsg] = useState("");
  const focusSeq = useRef(0);
  const [searched, setSearched] = useState<SearchHit | null>(null);

  const b = bounds;
  const qs = b
    ? new URLSearchParams({
        sw_lat: String(b.sw_lat),
        sw_lng: String(b.sw_lng),
        ne_lat: String(b.ne_lat),
        ne_lng: String(b.ne_lng),
        with_items: String(withItems),
        limit: "3000",
        ...(kind ? { kind } : {}),
      })
    : null;
  const { data, error, loading, reload, updatedAt } = useLoad<{
    orgs: MapOrg[];
    total: number;
    truncated: boolean;
  }>(qs ? `/orgs/map?${qs}` : null, { refreshMs: 60000 }); // 지도는 기관이 많아 1분마다만 갱신
  const orgs = data?.orgs ?? [];
  const sorted = [...orgs].sort(
    (a, b) =>
      Number(b.my_school) - Number(a.my_school) ||
      b.available_now - a.available_now,
  );
  const selected = orgs.find((o) => o.id === selectedId) ?? null;

  function locate() {
    setGeoMsg("");
    if (!navigator.geolocation)
      return setGeoMsg("이 브라우저는 위치 확인을 지원하지 않습니다.");
    navigator.geolocation.getCurrentPosition(
      (p) =>
        setFocus({
          lat: p.coords.latitude,
          lng: p.coords.longitude,
          level: 5,
          key: ++focusSeq.current,
        }),
      () => setGeoMsg("위치 권한이 없어 현재 위치로 이동하지 못했습니다."),
      { timeout: 8000 },
    );
  }

  function pick(o: MapOrg) {
    setSelectedId(o.id);
    setSearched(null);
    setFocus({ lat: o.lat, lng: o.lng, key: ++focusSeq.current });
  }

  function pickSearch(h: SearchHit) {
    setSearched(h);
    setSelectedId(h.id);
    if (h.lat != null && h.lng != null) {
      setFocus({ lat: h.lat, lng: h.lng, level: 5, key: ++focusSeq.current });
    }
  }

  return (
    <>
      <PageHeader
        title="지도에서 기관 찾기"
        desc="학교·주민센터를 지도에서 고르고, 그 기관에서 빌릴 수 있는 물품을 확인하세요. 표시: 지금 빌릴 수 있는 수 / 전체 물품 수"
        actions={<LiveBadge updatedAt={updatedAt} />}
      />
      <MapSearch kind={kind} onPick={pickSearch} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="map-kind">
          기관 종류
        </label>
        <select
          id="map-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value as OrgKind | "")}
          className={`${inputBase} w-40`}
        >
          <option value="">모든 기관</option>
          <option value="school">학교</option>
          <option value="community_center">주민센터</option>
        </select>
        <label className="flex items-center gap-2 text-sm font-semibold text-navy-800">
          <input
            type="checkbox"
            checked={withItems}
            onChange={(e) => setWithItems(e.target.checked)}
            className="size-4 accent-teal-700"
          />
          물품이 등록된 기관만
        </label>
        <button type="button" className={btn.secondary} onClick={locate}>
          📍 내 위치
        </button>
        {user.student.status === "approved" && user.student.school && (
          <Link
            href={`/items?org=${user.student.school.id}`}
            className={btn.secondary}
          >
            🏫 우리 학교 물품
          </Link>
        )}
      </div>
      {geoMsg && (
        <p role="alert" className="mb-2 text-sm font-semibold text-rose-800">
          {geoMsg}
        </p>
      )}
      {mapError && (
        <p
          role="status"
          className="mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950"
        >
          {mapError} 기본 지도(OpenStreetMap)로 표시합니다.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="h-[55vh] min-h-80 overflow-hidden rounded-xl border border-navy-100 bg-navy-50 shadow-sm lg:h-[70vh]">
          {engine === "kakao" ? (
            <KakaoMap
              orgs={orgs}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onBounds={setBounds}
              focus={focus}
              onError={(msg) => {
                setMapError(msg);
                setEngine("osm");
              }}
            />
          ) : (
            <OsmMap
              orgs={orgs}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onBounds={setBounds}
              focus={focus}
            />
          )}
        </div>
        <div className="grid content-start gap-3">
          {!selected && searched && searched.id === selectedId && (
            <section className="rounded-xl border-2 border-navy-900 bg-white p-4 shadow-sm" aria-live="polite">
              <p className="text-xs font-semibold text-navy-600">
                {ORG_KIND_ICON[searched.kind]} {ORG_KIND_LABEL[searched.kind]} {searched.subtype && `· ${searched.subtype}`}
              </p>
              <h2 className="text-lg font-bold">{searched.name}</h2>
              <p className="text-sm text-navy-700">{searched.address}</p>
              <p className="mt-2 text-sm text-navy-700">
                {searched.lat == null
                  ? "아직 지도 위치가 등록되지 않은 기관입니다."
                  : withItems
                    ? "등록된 물품이 없어 지도에 표시되지 않았을 수 있습니다."
                    : ""}
              </p>
              <div className="mt-3 flex gap-2">
                <Link href={`/items?org=${searched.id}`} className={btn.primary}>
                  이 기관 물품 보기
                </Link>
                <button type="button" className={btn.secondary} onClick={() => setSearched(null)}>
                  닫기
                </button>
              </div>
            </section>
          )}
          {selected && (
            <section
              className="rounded-xl border-2 border-navy-900 bg-white p-4 shadow-sm"
              aria-live="polite"
            >
              <p className="text-xs font-semibold text-navy-600">
                {ORG_KIND_ICON[selected.kind]} {ORG_KIND_LABEL[selected.kind]}{" "}
                {selected.subtype && `· ${selected.subtype}`}
              </p>
              <h2 className="text-lg font-bold">{selected.name}</h2>
              <p className="text-sm text-navy-700">{selected.address}</p>
              <p className="mt-2 text-sm">
                지금 빌릴 수 있는 물품{" "}
                <strong className="text-teal-800">
                  {selected.available_now}개
                </strong>{" "}
                / 전체 {selected.items}개
              </p>
              {selected.members_only > 0 && (
                <p className="mt-1 text-xs text-indigo-900">
                  🎓 {selected.members_only}개는 이 학교 승인 학생 전용입니다
                  {selected.my_school ? " (우리 학교)" : ""}.
                </p>
              )}
              <div className="mt-3 flex gap-2">
                <Link
                  href={`/items?org=${selected.id}`}
                  className={btn.primary}
                >
                  이 기관 물품 보기
                </Link>
                <button
                  type="button"
                  className={btn.secondary}
                  onClick={() => setSelectedId(null)}
                >
                  닫기
                </button>
              </div>
            </section>
          )}
          {loading && !data ? (
            <Loading
              label={!bounds ? "지도를 불러오는 중…" : "기관을 찾는 중…"}
            />
          ) : error ? (
            <ErrorState message={error} onRetry={reload} />
          ) : orgs.length === 0 ? (
            <Empty title="이 지도 범위에 표시할 기관이 없습니다.">
              {withItems ? (
                <>
                  지금은 물품이 등록된 기관만 보여 주고 있어요.{" "}
                  <button
                    type="button"
                    className="font-semibold text-teal-800 underline"
                    onClick={() => setWithItems(false)}
                  >
                    모든 기관 보기
                  </button>
                </>
              ) : (
                "지도를 축소하거나 다른 지역으로 이동해 보세요."
              )}
            </Empty>
          ) : (
            <section className="rounded-xl border border-navy-100 bg-white shadow-sm">
              <h2 className="border-b border-navy-100 px-4 py-2.5 text-sm font-bold">
                지도 범위 안 기관 {data?.total ?? orgs.length}곳
                {data?.truncated && (
                  <span className="ml-1 font-normal text-navy-600">
                    (일부만 표시 — 지도를 확대하세요)
                  </span>
                )}
              </h2>
              <ul className="max-h-[60vh] divide-y divide-navy-50 overflow-y-auto">
                {sorted.map((o) => (
                  <li key={o.id}>
                    <button
                      type="button"
                      onClick={() => pick(o)}
                      aria-pressed={o.id === selectedId}
                      className={`flex w-full items-start justify-between gap-2 px-4 py-2.5 text-left text-sm hover:bg-navy-50 ${o.id === selectedId ? "bg-teal-50" : ""}`}
                    >
                      <span>
                        <span aria-hidden>{ORG_KIND_ICON[o.kind]} </span>
                        <span className="font-semibold">{o.name}</span>
                        {o.my_school && (
                          <span className="ml-1 rounded bg-indigo-100 px-1 text-xs font-bold text-indigo-900">
                            우리 학교
                          </span>
                        )}
                        <span className="block text-xs text-navy-600">
                          {o.address}
                        </span>
                      </span>
                      <span
                        className={`shrink-0 text-xs font-bold ${o.available_now ? "text-teal-800" : "text-slate-500"}`}
                      >
                        {o.available_now}/{o.items}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
