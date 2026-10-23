"use client";

import Link from "next/link";
import { useState } from "react";
import { btn, Empty, ErrorState, FlashMessage, inputCls, ItemBadge, labelCls, Loading, PageHeader, ReportBadge, type Flash } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { REPORT_LABEL } from "@/lib/labels";
import { fmtDateTime, fmtRange } from "@/lib/time";
import type { Report, ReportStatus, Reservation } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

const FILTERS = [
  ["open", "미처리 (접수·수리 중)"],
  ["received", "접수"],
  ["in_progress", "수리 중"],
  ["resolved", "처리 완료"],
  ["dismissed", "이상 없음"],
  ["", "전체"],
] as const;

export default function AdminReports() {
  const [filter, setFilter] = useState<string>("open");
  const list = useLoad<{ reports: Report[] }>(`/admin/reports${filter ? `?status=${filter}` : ""}`);
  const rows = list.data?.reports ?? [];

  return (
    <>
      <PageHeader title="고장 신고 관리" desc="신고 내용을 확인하고 처리 상태와 메모를 기록합니다. 수리 중인 물품은 신규 승인과 대여 시작이 막힙니다." />
      <div className="mb-4 flex gap-1 overflow-x-auto pb-1" role="group" aria-label="처리 상태 필터">
        {FILTERS.map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={filter === k}
            onClick={() => setFilter(k)}
            className={`shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-semibold ${
              filter === k ? "border-navy-900 bg-navy-900 text-white" : "border-navy-200 bg-white text-navy-700 hover:bg-navy-50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {list.loading && !list.data ? (
        <Loading />
      ) : list.error ? (
        <ErrorState message={list.error} onRetry={list.reload} />
      ) : rows.length === 0 ? (
        <Empty title="해당하는 고장 신고가 없습니다." />
      ) : (
        <ul className="grid gap-4 lg:grid-cols-2">
          {rows.map((r) => (
            <ReportCard key={`${r.id}-${r.updated_at}`} report={r} onSaved={list.reload} />
          ))}
        </ul>
      )}
    </>
  );
}

function ReportCard({ report, onSaved }: { report: Report; onSaved: () => void }) {
  const [status, setStatus] = useState<ReportStatus>(report.status);
  const [note, setNote] = useState(report.admin_note);
  const [itemAction, setItemAction] = useState<"none" | "set_repair" | "set_normal">("none");
  const [flash, setFlash] = useState<Flash>(null);
  const [affected, setAffected] = useState<Reservation[]>([]);
  const [saving, setSaving] = useState(false);
  const item = report.item;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFlash(null);
    try {
      const res = await api<{ report: Report; affected: Reservation[] }>(`/admin/reports/${report.id}`, {
        method: "PATCH",
        body: { status, admin_note: note, item_action: itemAction },
      });
      setAffected(res.affected);
      setFlash({ kind: "ok", text: "저장했습니다." });
      if (!res.affected.length) onSaved();
    } catch (err) {
      setFlash({ kind: "error", text: `저장하지 못했습니다: ${errorMessage(err)}` });
    } finally {
      setSaving(false);
    }
  }

  return (
    <li className="rounded-xl border border-navy-100 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <Link href={`/items/${item?.id}`} className="font-bold hover:underline">
            {item?.name} <span className="font-mono text-sm font-normal">{item?.asset_code}</span>
          </Link>
          <p className="text-xs text-navy-600">
            #{report.id} · {report.reporter?.name} · {fmtDateTime(report.created_at)}
            {report.reservation_id && ` · 예약 #${report.reservation_id}`}
          </p>
        </div>
        <dl className="grid grid-cols-[auto_auto] items-center gap-x-2 gap-y-1 text-xs font-semibold text-navy-600">
          <dt>신고</dt>
          <dd><ReportBadge status={report.status} /></dd>
          {item && (
            <>
              <dt>물품</dt>
              <dd><ItemBadge status={item.status} /></dd>
            </>
          )}
        </dl>
      </div>
      <p className="mt-3 whitespace-pre-line rounded-md bg-navy-50 p-3 text-sm">{report.description}</p>
      <form onSubmit={save} className="mt-3 grid gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={labelCls}>
            처리 상태
            <select value={status} onChange={(e) => setStatus(e.target.value as ReportStatus)} className={inputCls}>
              {(Object.keys(REPORT_LABEL) as ReportStatus[]).map((s) => (
                <option key={s} value={s} disabled={s === "received" && report.status !== "received"}>
                  {REPORT_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
          <label className={labelCls}>
            물품 상태 변경
            <select value={itemAction} onChange={(e) => setItemAction(e.target.value as typeof itemAction)} className={inputCls} disabled={item?.status === "retired"}>
              <option value="none">변경 안 함 (현재: {item?.status === "repair" ? "수리 중" : item?.status === "retired" ? "보관 종료" : "정상"})</option>
              <option value="set_repair">수리 중으로 전환</option>
              <option value="set_normal">정상으로 복구</option>
            </select>
          </label>
        </div>
        <label className={labelCls}>
          처리 메모
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} className={inputCls} placeholder="예: 부품 주문함, 수리 완료 예정일" />
        </label>
        <FlashMessage flash={flash} />
        {affected.length > 0 && (
          <div role="alert" className="rounded-lg border border-orange-300 bg-orange-50 p-3 text-sm">
            <p className="font-bold text-orange-900">수리 전환으로 영향을 받는 예약 {affected.length}건</p>
            <ul className="mt-1 grid gap-0.5">
              {affected.map((a) => (
                <li key={a.id}>#{a.id} · {a.user?.name} · {fmtRange(a.start_at, a.end_at)} · {a.status_label}</li>
              ))}
            </ul>
            <div className="mt-2 flex gap-2">
              <Link href="/admin/reservations?tab=all" className={btn.small}>예약 관리로 이동</Link>
              <button type="button" className={btn.small} onClick={onSaved}>확인</button>
            </div>
          </div>
        )}
        <button type="submit" disabled={saving} className={`${btn.primary} justify-self-start`}>
          {saving ? "저장 중…" : "처리 내용 저장"}
        </button>
      </form>
    </li>
  );
}
