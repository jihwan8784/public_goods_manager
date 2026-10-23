"use client";

import Link from "next/link";
import { useState } from "react";
import Dialog from "@/components/Dialog";
import ItemThumb from "@/components/ItemThumb";
import {
  btn,
  Card,
  Empty,
  ErrorState,
  FlashMessage,
  inputCls,
  labelCls,
  Loading,
  PageHeader,
  ReportBadge,
  ReservationBadge,
  type Flash,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { dueText, fmtDateTime, fmtRange } from "@/lib/time";
import type { Report, Reservation } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type Tab = "active" | "past";

export default function MyReservations() {
  const [tab, setTab] = useState<Tab>("active");
  const list = useLoad<{ reservations: Reservation[] }>(`/reservations/mine?scope=${tab}`);
  const reports = useLoad<{ reports: Report[] }>("/reports/mine");
  const [flash, setFlash] = useState<Flash>(null);
  const [dialog, setDialog] = useState<{ kind: "cancel" | "return"; r: Reservation } | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function confirm() {
    if (!dialog) return;
    setBusy(true);
    try {
      if (dialog.kind === "cancel") {
        await api(`/reservations/${dialog.r.id}/cancel`, { body: { reason: note || null } });
        setFlash({ kind: "ok", text: `${dialog.r.item?.asset_code} 예약을 취소했습니다.` });
      } else {
        await api(`/reservations/${dialog.r.id}/return-request`, { body: { note: note || null } });
        setFlash({ kind: "ok", text: "반납 요청을 보냈습니다. 관리자가 실물을 확인하면 반납 완료됩니다." });
      }
      setDialog(null);
      await list.reload();
    } catch (e) {
      setFlash({ kind: "error", text: errorMessage(e) });
      setDialog(null);
    } finally {
      setBusy(false);
    }
  }

  const rows = list.data?.reservations ?? [];

  return (
    <>
      <PageHeader
        title="나의 예약·대여"
        desc="예약 상태와 반납 기한을 확인하고, 취소·반납 요청을 할 수 있습니다."
        actions={
          <Link href="/items" className={btn.primary}>
            새 예약 신청
          </Link>
        }
      />
      <div role="tablist" aria-label="내역 구분" className="mb-4 inline-flex rounded-lg border border-navy-200 bg-white p-1">
        {(
          [
            ["active", "진행 중"],
            ["past", "지난 내역"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            onClick={() => setTab(k)}
            className={`rounded-md px-4 py-1.5 text-sm font-semibold ${tab === k ? "bg-navy-900 text-white" : "text-navy-700 hover:bg-navy-50"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mb-4">
        <FlashMessage flash={flash} onClose={() => setFlash(null)} />
      </div>

      {list.loading && !list.data ? (
        <Loading />
      ) : list.error ? (
        <ErrorState message={list.error} onRetry={list.reload} />
      ) : rows.length === 0 ? (
        <Empty title={tab === "active" ? "진행 중인 예약·대여가 없습니다." : "지난 내역이 없습니다."}>
          <Link href="/items" className="font-semibold text-teal-800 underline">
            물품 찾아보기
          </Link>
        </Empty>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {rows.map((r) => (
            <li key={r.id} className={`rounded-xl border bg-white p-4 shadow-sm ${r.overdue ? "border-rose-300" : "border-navy-100"}`}>
              <div className="flex gap-3">
                {r.item && <ItemThumb item={r.item} size="sm" />}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <Link href={`/items/${r.item?.id}`} className="font-bold underline-offset-2 hover:underline">
                      {r.item?.name} <span className="font-mono text-sm font-normal text-navy-600">{r.item?.asset_code}</span>
                    </Link>
                    <ReservationBadge status={r.status} overdue={r.overdue} />
                  </div>
                  <p className="mt-1 text-sm text-navy-800">{fmtRange(r.start_at, r.end_at)}</p>
                  <p className="text-sm text-navy-600">목적: {r.purpose}</p>
                </div>
              </div>
              {(r.status === "in_use" || r.status === "return_requested") && (
                <p className={`mt-3 rounded-md px-3 py-2 text-sm ${r.overdue ? "bg-rose-50 font-bold text-rose-800" : "bg-teal-50 text-teal-900"}`}>
                  반납 기한 {fmtDateTime(r.end_at)} · {dueText(r.end_at)}
                </p>
              )}
              {r.status === "return_requested" && (
                <p className="mt-2 text-xs text-navy-600">반납 요청됨 ({r.return_requested_at && fmtDateTime(r.return_requested_at)}) · 관리자 확인 대기</p>
              )}
              {r.status === "approved" && (
                <p className="mt-2 text-xs text-navy-600">예약 확정 · 아직 대여 시작 전입니다. 시작 시각에 관리자에게 물품을 받으세요.</p>
              )}
              {r.reject_reason && <p className="mt-2 text-sm text-rose-800">거절 사유: {r.reject_reason}</p>}
              {r.cancel_reason && <p className="mt-2 text-sm text-navy-600">취소 사유: {r.cancel_reason}</p>}
              {r.status === "returned" && (
                <p className="mt-2 text-xs text-navy-600">
                  {r.returned_at && fmtDateTime(r.returned_at)} 반납 완료 · {r.return_condition === "needs_repair" ? "수리 필요로 확인됨" : "정상 확인"}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {(r.status === "pending" || r.status === "approved") && (
                  <button type="button" className={btn.danger} onClick={() => { setNote(""); setDialog({ kind: "cancel", r }); }}>
                    예약 취소
                  </button>
                )}
                {r.status === "in_use" && (
                  <button type="button" className={btn.primary} onClick={() => { setNote(""); setDialog({ kind: "return", r }); }}>
                    반납 요청
                  </button>
                )}
                {(r.status === "in_use" || r.status === "return_requested" || r.status === "returned") && r.item && (
                  <Link href={`/items/${r.item.id}?reservation=${r.id}#report`} className={btn.secondary}>
                    고장·파손 신고
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <Card className="mt-8">
        <h2 className="text-lg font-bold">내 고장 신고</h2>
        {reports.loading && !reports.data ? (
          <Loading />
        ) : reports.error ? (
          <ErrorState message={reports.error} onRetry={reports.reload} />
        ) : !reports.data?.reports.length ? (
          <p className="mt-2 text-sm text-navy-600">접수한 고장 신고가 없습니다.</p>
        ) : (
          <ul className="mt-3 divide-y divide-navy-100">
            {reports.data.reports.map((rep) => (
              <li key={rep.id} className="py-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold">
                    {rep.item?.name} <span className="font-mono text-navy-600">{rep.item?.asset_code}</span>
                  </span>
                  <ReportBadge status={rep.status} />
                </div>
                <p className="mt-1 text-navy-800">{rep.description}</p>
                {rep.admin_note && <p className="mt-1 text-navy-600">관리자 메모: {rep.admin_note}</p>}
                <p className="mt-1 text-xs text-navy-500">{fmtDateTime(rep.created_at)} 접수</p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Dialog
        open={!!dialog}
        title={dialog?.kind === "cancel" ? "예약을 취소할까요?" : "반납을 요청할까요?"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <div className="grid gap-4">
            <p className="text-sm">
              <strong>{dialog.r.item?.name} ({dialog.r.item?.asset_code})</strong>
              <br />
              {fmtRange(dialog.r.start_at, dialog.r.end_at)}
            </p>
            {dialog.kind === "return" && (
              <p className="rounded-md bg-navy-50 p-3 text-sm">
                반납 요청 후 관리자가 실물을 확인해야 반납이 완료됩니다. 물품은 보관 장소나 관리자에게 직접 전달해 주세요.
              </p>
            )}
            <label className={labelCls}>
              {dialog.kind === "cancel" ? "취소 사유 (선택)" : "전달 메모 (선택)"}
              <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} className={inputCls} />
            </label>
            <div className="flex justify-end gap-2">
              <button type="button" className={btn.secondary} onClick={() => setDialog(null)}>
                닫기
              </button>
              <button type="button" disabled={busy} className={dialog.kind === "cancel" ? btn.danger : btn.primary} onClick={confirm}>
                {busy ? "처리 중…" : dialog.kind === "cancel" ? "예약 취소" : "반납 요청"}
              </button>
            </div>
          </div>
        )}
      </Dialog>
    </>
  );
}
