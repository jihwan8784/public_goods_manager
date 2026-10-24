"use client";

import Link from "next/link";
import { useState } from "react";
import { btn, Card, Empty, ErrorState, FlashMessage, inputBase, inputCls, labelCls, Loading, PageHeader, type Flash } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { ORG_KIND_ICON, ORG_KIND_LABEL } from "@/lib/labels";
import { fmtDateTime } from "@/lib/time";
import type { OrgFull, OrgKind } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type Run = {
  id: number;
  kind: string;
  status: "running" | "ok" | "error";
  message: string;
  created: number;
  updated: number;
  deactivated: number;
  geocoded: number;
  started_at: string;
  finished_at: string | null;
};
type SyncStatus = {
  runs: Run[];
  orgs_by_kind: Record<string, number>;
  geocode: Record<string, number>;
  neis_key: boolean;
  kakao_key: boolean;
  cron_secret: boolean;
};
type OrgRow = OrgFull & { items: number; available_now: number; admins: { id: number; name: string; email: string }[] };

const GEO_LABEL: Record<string, string> = { ok: "좌표 확인", manual: "직접 지정", pending: "좌표 찾는 중", failed: "좌표 못 찾음" };

export default function AdminOrgs() {
  const sync = useLoad<SyncStatus>("/admin/sync");
  const [flash, setFlash] = useState<Flash>(null);
  const [syncing, setSyncing] = useState(false);

  async function runSync(schools: boolean) {
    setSyncing(true);
    setFlash(null);
    try {
      const res = await api<{ run: Run }>(`/admin/sync?schools=${schools}`, { method: "POST" });
      setFlash({ kind: res.run.status === "ok" ? "ok" : "error", text: res.run.message || "완료" });
    } catch (e) {
      setFlash({ kind: "error", text: errorMessage(e) });
    } finally {
      setSyncing(false);
      sync.reload();
    }
  }

  const s = sync.data;
  return (
    <>
      <PageHeader title="기관 관리" desc="공공데이터에서 학교·주민센터 목록을 가져오고, 기관마다 관리자를 지정합니다." />
      <div className="mb-4">
        <FlashMessage flash={flash} onClose={() => setFlash(null)} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="font-bold">공공데이터 자동 동기화</h2>
          {sync.loading && !s ? (
            <Loading />
          ) : sync.error ? (
            <ErrorState message={sync.error} onRetry={sync.reload} />
          ) : s ? (
            <div className="mt-3 grid gap-3 text-sm">
              <ul className="grid gap-1">
                <KeyRow ok={s.neis_key} label="교육청 NEIS 학교정보 키 (NEIS_API_KEY)" />
                <KeyRow ok={s.kakao_key} label="카카오 주소→좌표 키 (KAKAO_REST_API_KEY, 선택 — 없으면 위치 CSV 로 좌표 채우기)" />
                <KeyRow ok={s.cron_secret} label="매일 자동 실행 (CRON_SECRET)" />
              </ul>
              <p>
                등록된 기관: 학교 {s.orgs_by_kind.school ?? 0}곳 · 주민센터 {s.orgs_by_kind.community_center ?? 0}곳 · 기타{" "}
                {s.orgs_by_kind.other ?? 0}곳
              </p>
              <p className="text-navy-700">
                좌표: 확인 {(s.geocode.ok ?? 0) + (s.geocode.manual ?? 0)} · 찾는 중 {s.geocode.pending ?? 0} · 실패 {s.geocode.failed ?? 0}
              </p>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={btn.primary} disabled={syncing || !s.neis_key} onClick={() => runSync(true)}>
                  {syncing ? "동기화 중… (최대 1분)" : "학교 목록 지금 동기화"}
                </button>
                <button type="button" className={btn.secondary} disabled={syncing || !s.kakao_key} onClick={() => runSync(false)}>
                  좌표만 이어서 찾기
                </button>
              </div>
              <p className="text-xs text-navy-600">
                매일 새벽 3시(KST)에 자동으로 새 학교·폐교·주소 변경을 반영하고 좌표를 찾습니다. 학교가 많아 첫 좌표 확인은 여러 번에 나눠 진행됩니다.
              </p>
              <h3 className="mt-2 font-semibold">최근 실행</h3>
              {s.runs.length === 0 ? (
                <p className="text-navy-600">아직 실행 기록이 없습니다.</p>
              ) : (
                <ul className="grid gap-1.5">
                  {s.runs.map((r) => (
                    <li key={r.id} className={`rounded-md px-3 py-2 ${r.status === "error" ? "bg-rose-50 text-rose-900" : "bg-navy-50"}`}>
                      <span className="font-semibold">
                        {r.status === "ok" ? "✔ 성공" : r.status === "error" ? "✕ 실패" : "… 진행 중"}
                      </span>{" "}
                      · {fmtDateTime(r.started_at)} · {r.kind}
                      <span className="block text-xs">{r.message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </Card>
        <div className="grid content-start gap-6">
          <CsvImport onDone={(text, ok) => { setFlash({ kind: ok ? "ok" : "error", text }); sync.reload(); }} />
          <ManualOrg onDone={(text) => setFlash({ kind: "ok", text })} />
        </div>
      </div>
      <OrgList onFlash={setFlash} />
    </>
  );
}

function KeyRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className={ok ? "text-teal-900" : "text-amber-900"}>
      {ok ? "✔" : "✕"} {label} {ok ? "설정됨" : "— 미설정"}
    </li>
  );
}

function CsvImport({ onDone }: { onDone: (text: string, ok: boolean) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<OrgKind>("community_center");
  const [replace, setReplace] = useState(false);
  const [coordsOnly, setCoordsOnly] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return onDone("CSV 파일을 선택해 주세요.", false);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", kind);
      form.append("replace", String(replace));
      form.append("coords_only", String(coordsOnly));
      const res = await api<{ run: Run }>("/admin/orgs/import", { form, method: "POST" });
      onDone(
        coordsOnly
          ? res.run.message
          : `가져오기 완료: 추가 ${res.run.created} · 변경 ${res.run.updated} · 비활성 ${res.run.deactivated}`,
        true,
      );
    } catch (err) {
      onDone(errorMessage(err), false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="font-bold">CSV 로 기관·좌표 가져오기</h2>
      <p className="mt-1 text-xs text-navy-600">
        공공데이터포털(data.go.kr)에서 받은 행정복지센터 목록 CSV 를 올리세요. &lsquo;기관명/행정복지센터명&rsquo;, &lsquo;도로명주소&rsquo; 열이 필요하고
        &lsquo;위도/경도&rsquo; 열이 있으면 그대로 씁니다. 같은 파일을 다시 올리면 중복 없이 갱신됩니다.
      </p>
      <form onSubmit={submit} className="mt-3 grid gap-3">
        <label className={labelCls}>
          CSV 파일 (UTF-8 또는 CP949)
          <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
        </label>
        <label className={labelCls}>
          기관 종류
          <select value={kind} onChange={(e) => setKind(e.target.value as OrgKind)} className={inputCls}>
            <option value="community_center">주민센터(행정복지센터)</option>
            <option value="school">학교</option>
            <option value="other">기타 기관</option>
          </select>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={coordsOnly} onChange={(e) => setCoordsOnly(e.target.checked)} className="mt-0.5 size-4 accent-teal-700" />
          <span>
            이미 있는 기관에 <strong>좌표만 채우기</strong> (새 기관은 만들지 않음)
            <span className="block text-xs text-navy-600">
              학교: 공공데이터포털 &lsquo;전국초중등학교위치표준데이터&rsquo; CSV 를 기관 종류 &lsquo;학교&rsquo;로 올리면 NEIS 로 가져온 학교에 위도·경도가 들어갑니다. 카카오 키가 없어도 지도에 표시됩니다.
            </span>
          </span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={replace} disabled={coordsOnly} onChange={(e) => setReplace(e.target.checked)} className="size-4 accent-teal-700" />
          파일에 없는 기존 CSV 기관은 비활성 처리 (전체 목록 파일일 때만)
        </label>
        <button type="submit" disabled={busy} className={`${btn.secondary} justify-self-start`}>
          {busy ? "가져오는 중…" : "가져오기"}
        </button>
      </form>
    </Card>
  );
}

function ManualOrg({ onDone }: { onDone: (text: string) => void }) {
  const [v, setV] = useState({ kind: "other" as OrgKind, name: "", address: "", lat: "", lng: "" });
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!v.name.trim()) return setError("기관 이름을 입력해 주세요.");
    const lat = v.lat ? Number(v.lat) : null;
    const lng = v.lng ? Number(v.lng) : null;
    if ((lat === null) !== (lng === null) || (lat !== null && (Number.isNaN(lat) || Number.isNaN(lng!)))) return setError("위도·경도는 둘 다 숫자로 입력하거나 둘 다 비워 두세요.");
    try {
      await api("/admin/orgs", { body: { kind: v.kind, name: v.name, address: v.address, lat, lng } });
      onDone(`${v.name} 기관을 추가했습니다.`);
      setV({ kind: "other", name: "", address: "", lat: "", lng: "" });
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <Card>
      <h2 className="font-bold">기관 직접 추가</h2>
      <form onSubmit={submit} className="mt-3 grid gap-3 sm:grid-cols-2" noValidate>
        <label className={labelCls}>
          종류
          <select value={v.kind} onChange={(e) => setV({ ...v, kind: e.target.value as OrgKind })} className={inputCls}>
            <option value="other">기타 기관</option>
            <option value="community_center">주민센터</option>
            <option value="school">학교</option>
          </select>
        </label>
        <label className={labelCls}>
          이름
          <input value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} className={inputCls} />
        </label>
        <label className={`${labelCls} sm:col-span-2`}>
          주소 (좌표를 비우면 주소로 자동 검색)
          <input value={v.address} onChange={(e) => setV({ ...v, address: e.target.value })} className={inputCls} />
        </label>
        <label className={labelCls}>
          위도 (선택)
          <input inputMode="decimal" value={v.lat} onChange={(e) => setV({ ...v, lat: e.target.value })} className={inputCls} />
        </label>
        <label className={labelCls}>
          경도 (선택)
          <input inputMode="decimal" value={v.lng} onChange={(e) => setV({ ...v, lng: e.target.value })} className={inputCls} />
        </label>
        {error && <p role="alert" className="text-sm font-semibold text-rose-800 sm:col-span-2">{error}</p>}
        <button type="submit" className={`${btn.secondary} justify-self-start`}>
          추가
        </button>
      </form>
    </Card>
  );
}

function OrgList({ onFlash }: { onFlash: (f: Flash) => void }) {
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState({ q: "", kind: "", hasItems: true, geocode: "" });
  const qs = new URLSearchParams({ limit: "50", has_items: String(applied.hasItems) });
  if (applied.q) qs.set("q", applied.q);
  if (applied.kind) qs.set("kind", applied.kind);
  if (applied.geocode) qs.set("geocode", applied.geocode);
  const list = useLoad<{ total: number; orgs: OrgRow[] }>(`/admin/orgs?${qs}`);

  return (
    <Card className="mt-6">
      <h2 className="font-bold">기관 목록 · 관리자 지정</h2>
      <form
        role="search"
        className="mt-3 flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied({ ...applied, q: q.trim() });
        }}
      >
        <label className="sr-only" htmlFor="org-q">기관 검색</label>
        <input id="org-q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="기관 이름 또는 주소" className={`${inputCls} max-w-xs`} />
        <label className="sr-only" htmlFor="org-kind">종류</label>
        <select id="org-kind" value={applied.kind} onChange={(e) => setApplied({ ...applied, kind: e.target.value })} className={`${inputBase} w-36`}>
          <option value="">모든 종류</option>
          <option value="school">학교</option>
          <option value="community_center">주민센터</option>
          <option value="other">기타</option>
        </select>
        <label className="sr-only" htmlFor="org-geo">좌표 상태</label>
        <select id="org-geo" value={applied.geocode} onChange={(e) => setApplied({ ...applied, geocode: e.target.value })} className={`${inputBase} w-40`}>
          <option value="">좌표 상태 전체</option>
          <option value="failed">좌표 못 찾음</option>
          <option value="pending">좌표 찾는 중</option>
          <option value="manual">직접 지정</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={applied.hasItems} onChange={(e) => setApplied({ ...applied, hasItems: e.target.checked })} className="size-4 accent-teal-700" />
          물품 있는 기관만
        </label>
        <button type="submit" className={btn.secondary}>검색</button>
      </form>
      {list.loading && !list.data ? (
        <Loading />
      ) : list.error ? (
        <ErrorState message={list.error} onRetry={list.reload} />
      ) : !list.data?.orgs.length ? (
        <div className="mt-4">
          <Empty title="해당하는 기관이 없습니다.">
            {applied.hasItems && "'물품 있는 기관만'을 끄고 이름으로 검색하면 관리자를 지정할 기관을 찾을 수 있어요."}
          </Empty>
        </div>
      ) : (
        <>
          <p className="mt-3 text-sm text-navy-600">
            {list.data.total}곳 중 {list.data.orgs.length}곳 표시
          </p>
          <ul className="mt-2 grid gap-3">
            {list.data.orgs.map((o) => (
              <OrgRowCard key={o.id} org={o} onChanged={list.reload} onFlash={onFlash} />
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

function OrgRowCard({ org, onChanged, onFlash }: { org: OrgRow; onChanged: () => void; onFlash: (f: Flash) => void }) {
  const [email, setEmail] = useState("");
  const [lat, setLat] = useState(org.lat?.toString() ?? "");
  const [lng, setLng] = useState(org.lng?.toString() ?? "");

  async function call(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      onFlash({ kind: "ok", text: ok });
      onChanged();
    } catch (e) {
      onFlash({ kind: "error", text: errorMessage(e) });
    }
  }

  return (
    <li className={`rounded-lg border p-4 ${org.active ? "border-navy-100" : "border-dashed border-slate-300 bg-slate-50"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-bold">
            {ORG_KIND_ICON[org.kind]} {org.name}
            {!org.active && <span className="ml-2 text-xs font-semibold text-slate-600">(비활성)</span>}
          </p>
          <p className="text-xs text-navy-600">
            {ORG_KIND_LABEL[org.kind]} {org.subtype && `· ${org.subtype}`} · {org.address || "주소 없음"} · 출처 {org.source}
          </p>
          <p className="text-xs text-navy-600">
            {GEO_LABEL[org.geocode_status]} · 물품 {org.items}개 (지금 가능 {org.available_now})
          </p>
        </div>
        <Link href={`/items?org=${org.id}`} className={btn.small}>
          물품 보기
        </Link>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="text-sm font-semibold">기관 관리자</p>
          {org.admins.length === 0 ? (
            <p className="text-xs text-navy-600">지정된 관리자가 없습니다.</p>
          ) : (
            <ul className="mt-1 grid gap-1 text-sm">
              {org.admins.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2">
                  <span>
                    {a.name} <span className="text-xs text-navy-600">{a.email}</span>
                  </span>
                  <button
                    type="button"
                    className="text-xs font-semibold text-rose-800 underline"
                    onClick={() => call(() => api(`/admin/orgs/${org.id}/admins/${a.id}`, { method: "DELETE" }), `${a.name}님의 관리자 지정을 해제했습니다.`)}
                  >
                    해제
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form
            className="mt-2 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!email.trim()) return;
              call(() => api(`/admin/orgs/${org.id}/admins`, { body: { email } }), `${email} 님을 ${org.name} 관리자로 지정했습니다.`);
              setEmail("");
            }}
          >
            <label className="sr-only" htmlFor={`admin-${org.id}`}>관리자로 지정할 회원 이메일</label>
            <input id={`admin-${org.id}`} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="가입한 회원 이메일" className={`${inputCls} py-1.5 text-sm`} />
            <button type="submit" className={btn.small}>지정</button>
          </form>
        </div>
        <div>
          <p className="text-sm font-semibold">위치 보정 · 상태</p>
          <form
            className="mt-1 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const la = Number(lat);
              const ln = Number(lng);
              if (!lat || !lng || Number.isNaN(la) || Number.isNaN(ln)) return onFlash({ kind: "error", text: "위도·경도를 숫자로 입력해 주세요." });
              call(() => api(`/admin/orgs/${org.id}`, { method: "PATCH", body: { lat: la, lng: ln } }), `${org.name} 좌표를 직접 지정했습니다.`);
            }}
          >
            <label className="sr-only" htmlFor={`lat-${org.id}`}>위도</label>
            <input id={`lat-${org.id}`} inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="위도" className={`${inputBase} w-28 py-1.5 text-sm`} />
            <label className="sr-only" htmlFor={`lng-${org.id}`}>경도</label>
            <input id={`lng-${org.id}`} inputMode="decimal" value={lng} onChange={(e) => setLng(e.target.value)} placeholder="경도" className={`${inputBase} w-28 py-1.5 text-sm`} />
            <button type="submit" className={btn.small}>좌표 저장</button>
          </form>
          <button
            type="button"
            className={`${btn.small} mt-2`}
            onClick={() =>
              call(
                () => api(`/admin/orgs/${org.id}`, { method: "PATCH", body: { active: !org.active } }),
                org.active ? `${org.name}을(를) 비활성 처리했습니다.` : `${org.name}을(를) 다시 활성화했습니다.`,
              )
            }
          >
            {org.active ? "비활성 처리" : "다시 활성화"}
          </button>
        </div>
      </div>
    </li>
  );
}
