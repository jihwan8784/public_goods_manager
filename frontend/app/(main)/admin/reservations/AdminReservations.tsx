"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import Dialog from "@/components/Dialog";
import {
  btn,
  Empty,
  ErrorState,
  FlashMessage,
  inputCls,
  ItemBadge,
  labelCls,
  Loading,
  PageHeader,
  ReservationBadge,
  type Flash,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { dueText, fmtDateTime, fmtRange } from "@/lib/time";
import type { Reservation } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

const TABS = [
  { key: "pending", label: "승인 대기", query: "status=pending" },
  { key: "approved", label: "인계 대기", query: "status=approved" },
  { key: "renting", label: "대여 중", query: "status=in_use,return_requested" },
  { key: "return_requested", label: "반납 확인", query: "status=return_requested" },
  { key: "overdue", label: "연체", query: "overdue=true" },
  { key: "done", label: "완료·종료", query: "status=returned,rejected,cancelled" },
  { key: "all", label: "전체", query: "" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

type DialogState =
  | { kind: "reject" | "cancel"; r: Reservation }
  | { kind: "return"; r: Reservation }
  | null;

export default function AdminReservations() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = (TABS.find((t) => t.key === params.get("tab"))?.key ?? "pending") as TabKey;
  const q = params.get("q") ?? "";
  const [qInput, setQInput] = useState(q);
  const tabDef = TABS.find((t) => t.key === tab)!;
  const query = [tabDef.query, q ? `q=${encodeURIComponent(q)}` : ""].filter(Boolean).join("&");
  const list = useLoad<{ reservations: Reservation[] }>(`/admin/reservations?${query}`);

  const [flash, setFlash] = useState<Flash>(null);
  const [affected, setAffected] = useState<Reservation[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [dialog, setDialog] = useState<DialogState>(null);
  const [reason, setReason] = useState("");
  const [condition, setCondition] = useState<"normal" | "needs_repair">("normal");
  const [dialogError, setDialogError] = useState("");

  function go(next: { tab?: string; q?: string }) {
    const p = new URLSearchParams();
    p.set("tab", next.tab ?? tab);
    const nq = next.q ?? q;
    if (nq) p.set("q", nq);
    router.replace(`${pathname}?${p.toString()}`);
  }

  async function act(r: Reservation, action: "approve" | "checkout", label: string) {
    setBusyId(r.id);
    setFlash(null);
    try {
      await api(`/admin/reservations/${r.id}/${action}`, { method: "POST" });
      setFlash({ kind: "ok", text: `#${r.id} ${r.item?.asset_code} ${label} 처리했습니다.` });
    } catch (e) {
      setFlash({ kind: "error", text: `#${r.id} ${label} 실패: ${errorMessage(e)}` });
    } finally {
      setBusyId(null);
      list.reload();
    }
  }

  function open(kind: "reject" | "cancel" | "return", r: Reservation) {
    setReason("");
    setCondition("normal");
    setDialogError("");
    setDialog({ kind, r });
  }

  async function submitDialog() {
    if (!dialog) return;
    const r = dialog.r;
    if ((dialog.kind === "reject" || dialog.kind === "cancel") && !reason.trim()) {
      setDialogError("사유를 입력해 주세요.");
      return;
    }
    setBusyId(r.id);
    try {
      if (dialog.kind === "return") {
        const res = await api<{ affected: Reservation[]; report_id: number | null }>(`/admin/reservations/${r.id}/return`, {
          body: { condition, note: reason || null },
        });
        setAffected(res.affected);
        setFlash({
          kind: "ok",
          text:
            condition === "needs_repair"
              ? `#${r.id} 반납 완료. 물품을 '수리 중'으로 바꾸고 고장 신고 #${res.report_id}을 만들었습니다.`
              : `#${r.id} 반납 완료 처리했습니다.`,
        });
      } else {
        await api(`/admin/reservations/${r.id}/${dialog.kind}`, { body: { reason } });
        setFlash({ kind: "ok", text: `#${r.id} ${dialog.kind === "reject" ? "거절" : "취소"} 처리했습니다.` });
      }
      setDialog(null);
    } catch (e) {
      setDialogError(errorMessage(e));
    } finally {
      setBusyId(null);
      list.reload();
    }
  }

  const rows = list.data?.reservations ?? [];

  function renderActions(r: Reservation) {
    const busy = busyId === r.id;
    return (
      <div className="flex flex-wrap gap-1.5">
        {r.status === "pending" && (
          <>
            <button
              type="button"
              className={btn.primary}
              disabled={busy || (r.conflicts?.length ?? 0) > 0 || r.item_blocked}
              onClick={() => act(r, "approve", "승인")}
            >
              승인
            </button>
            <button type="button" className={btn.danger} disabled={busy} onClick={() => open("reject", r)}>
              거절
            </button>
          </>
        )}
        {r.status === "approved" && (
          <>
            <button
              type="button"
              className={btn.primary}
              disabled={busy || (r.blockers?.length ?? 0) > 0}
              onClick={() => act(r, "checkout", "대여 시작")}
            >
              인계·대여 시작
            </button>
            <button type="button" className={btn.danger} disabled={busy} onClick={() => open("cancel", r)}>
              예약 취소
            </button>
          </>
        )}
        {(r.status === "in_use" || r.status === "return_requested") && (
          <button type="button" className={btn.primary} disabled={busy} onClick={() => open("return", r)}>
            실물 확인·반납 완료
          </button>
        )}
      </div>
    );
  }

  function renderWarnings(r: Reservation) {
    const msgs: { text: string; strong?: boolean }[] = [];
    if (r.item_blocked) msgs.push({ text: "물품이 수리 중이거나 보관 종료되어 승인할 수 없습니다.", strong: true });
    if (r.conflicts?.length) msgs.push({ text: `확정된 예약 #${r.conflicts.join(", #")}과 겹쳐 승인할 수 없습니다.`, strong: true });
    if (r.pending_overlaps?.length) msgs.push({ text: `승인 대기 #${r.pending_overlaps.join(", #")}과 기간이 겹칩니다. 하나만 승인됩니다.` });
    for (const b of r.blockers ?? []) msgs.push({ text: b, strong: !b.includes("분 전부터") });
    if (r.return_request_note) msgs.push({ text: `사용자 메모: ${r.return_request_note}` });
    if (!msgs.length) return null;
    return (
      <ul className="mt-1.5 grid gap-0.5 text-xs">
        {msgs.map((m) => (
          <li key={m.text} className={m.strong ? "font-semibold text-rose-800" : "text-navy-600"}>
            {m.strong ? "⚠ " : "· "}
            {m.text}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <>
      <PageHeader title="예약·대여 관리" desc="승인, 인계(대여 시작), 반납 확인을 순서대로 처리합니다. 승인만으로는 대여가 시작되지 않습니다." />

      <nav aria-label="상태별 보기" className="mb-4 flex gap-1 overflow-x-auto pb-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-current={tab === t.key ? "page" : undefined}
            onClick={() => go({ tab: t.key })}
            className={`shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-semibold ${
              tab === t.key ? "border-navy-900 bg-navy-900 text-white" : "border-navy-200 bg-white text-navy-700 hover:bg-navy-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <form
        role="search"
        className="mb-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          go({ q: qInput.trim() });
        }}
      >
        <label className="sr-only" htmlFor="admin-q">물품명·관리번호·사용자 이름 검색</label>
        <input id="admin-q" type="search" value={qInput} onChange={(e) => setQInput(e.target.value)} placeholder="물품명, 관리번호, 사용자 이름" className={`${inputCls} max-w-sm`} />
        <button type="submit" className={btn.secondary}>검색</button>
      </form>

      <div className="mb-4 grid gap-3">
        <FlashMessage flash={flash} onClose={() => setFlash(null)} />
        {affected.length > 0 && (
          <div role="alert" className="rounded-lg border border-orange-300 bg-orange-50 p-4 text-sm">
            <p className="font-bold text-orange-900">수리 전환으로 영향을 받는 예약 {affected.length}건</p>
            <ul className="mt-2 grid gap-1">
              {affected.map((a) => (
                <li key={a.id}>#{a.id} {a.item?.asset_code} · {a.user?.name} · {fmtRange(a.start_at, a.end_at)} · {a.status_label}</li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-orange-900">사용자에게 직접 안내한 뒤 필요하면 취소하거나 다른 물품으로 다시 신청하도록 해 주세요. (자동 알림은 보내지 않습니다)</p>
            <button type="button" className={`${btn.small} mt-2`} onClick={() => setAffected([])}>확인</button>
          </div>
        )}
      </div>

      {list.loading && !list.data ? (
        <Loading />
      ) : list.error ? (
        <ErrorState message={list.error} onRetry={list.reload} />
      ) : rows.length === 0 ? (
        <Empty title="해당하는 예약이 없습니다." />
      ) : (
        <>
          {/* 모바일 카드 */}
          <ul className="grid gap-3 lg:hidden">
            {rows.map((r) => (
              <li key={r.id} className={`rounded-xl border bg-white p-4 shadow-sm ${r.overdue ? "border-rose-300" : "border-navy-100"}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <Link href={`/items/${r.item?.id}`} className="font-bold hover:underline">
                      {r.item?.name} <span className="font-mono text-sm font-normal">{r.item?.asset_code}</span>
                    </Link>
                    <p className="text-sm text-navy-700">{r.user?.name} · #{r.id}</p>
                  </div>
                  <ReservationBadge status={r.status} overdue={r.overdue} />
                </div>
                <p className="mt-2 text-sm">{fmtRange(r.start_at, r.end_at)}</p>
                {(r.status === "in_use" || r.status === "return_requested") && (
                  <p className={`text-sm ${r.overdue ? "font-bold text-rose-800" : "text-navy-600"}`}>반납 기한 {dueText(r.end_at)}</p>
                )}
                <p className="text-sm text-navy-600">목적: {r.purpose}</p>
                {r.reject_reason && <p className="text-sm text-rose-800">거절 사유: {r.reject_reason}</p>}
                {r.cancel_reason && <p className="text-sm text-navy-600">취소 사유: {r.cancel_reason}</p>}
                {renderWarnings(r)}
                <div className="mt-3">{renderActions(r)}</div>
              </li>
            ))}
          </ul>
          {/* PC 표 */}
          <div className="hidden overflow-x-auto rounded-xl border border-navy-100 bg-white shadow-sm lg:block">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">예약·대여 목록</caption>
              <thead className="bg-navy-50 text-navy-700">
                <tr>
                  <th scope="col" className="px-3 py-3">#</th>
                  <th scope="col" className="px-3 py-3">물품</th>
                  <th scope="col" className="px-3 py-3">사용자 · 목적</th>
                  <th scope="col" className="px-3 py-3">기간 (KST)</th>
                  <th scope="col" className="px-3 py-3">상태</th>
                  <th scope="col" className="px-3 py-3">처리</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-100 align-top">
                {rows.map((r) => (
                  <tr key={r.id} className={r.overdue ? "bg-rose-50/60" : undefined}>
                    <td className="px-3 py-3 font-mono text-navy-600">{r.id}</td>
                    <td className="px-3 py-3">
                      <Link href={`/items/${r.item?.id}`} className="font-semibold hover:underline">{r.item?.name}</Link>
                      <div className="font-mono text-xs text-navy-600">{r.item?.asset_code}</div>
                      {r.item && r.item.status !== "normal" && <div className="mt-1"><ItemBadge status={r.item.status} /></div>}
                    </td>
                    <td className="px-3 py-3">
                      <div className="font-semibold">{r.user?.name}</div>
                      <div className="max-w-56 text-xs text-navy-600">{r.purpose}</div>
                    </td>
                    <td className="px-3 py-3">
                      {fmtRange(r.start_at, r.end_at)}
                      {(r.status === "in_use" || r.status === "return_requested") && (
                        <div className={`text-xs ${r.overdue ? "font-bold text-rose-800" : "text-navy-600"}`}>반납 기한 {dueText(r.end_at)}</div>
                      )}
                      {r.returned_at && <div className="text-xs text-navy-600">반납 {fmtDateTime(r.returned_at)} · {r.return_condition === "needs_repair" ? "수리 필요" : "정상"}</div>}
                    </td>
                    <td className="px-3 py-3">
                      <ReservationBadge status={r.status} overdue={r.overdue} />
                      {r.reject_reason && <div className="mt-1 max-w-48 text-xs text-rose-800">사유: {r.reject_reason}</div>}
                      {r.cancel_reason && <div className="mt-1 max-w-48 text-xs text-navy-600">사유: {r.cancel_reason}</div>}
                    </td>
                    <td className="px-3 py-3">
                      {renderActions(r)}
                      <div className="max-w-72">{renderWarnings(r)}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Dialog
        open={!!dialog}
        title={dialog?.kind === "reject" ? "예약 거절" : dialog?.kind === "cancel" ? "확정 예약 취소" : "반납 완료 처리"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              submitDialog();
            }}
          >
            <p className="text-sm">
              <strong>
                #{dialog.r.id} {dialog.r.item?.name} ({dialog.r.item?.asset_code})
              </strong>
              <br />
              {dialog.r.user?.name} · {fmtRange(dialog.r.start_at, dialog.r.end_at)}
            </p>
            {dialog.kind === "return" && (
              <fieldset className="grid gap-2">
                <legend className="text-sm font-semibold text-navy-700">실물 확인 결과</legend>
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" name="cond" checked={condition === "normal"} onChange={() => setCondition("normal")} className="accent-teal-700" />
                  정상 — 바로 다시 대여 가능
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" name="cond" checked={condition === "needs_repair"} onChange={() => setCondition("needs_repair")} className="accent-teal-700" />
                  수리 필요 — 물품을 &apos;수리 중&apos;으로 바꾸고 고장 신고 생성
                </label>
              </fieldset>
            )}
            <label className={labelCls}>
              {dialog.kind === "return" ? "확인 메모 (선택)" : "사유 (필수, 사용자에게 표시됨)"}
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={300} className={inputCls} aria-invalid={!!dialogError} />
            </label>
            {dialogError && <p role="alert" className="text-sm font-semibold text-rose-800">{dialogError}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" className={btn.secondary} onClick={() => setDialog(null)}>닫기</button>
              <button type="submit" disabled={busyId === dialog.r.id} className={dialog.kind === "return" ? btn.primary : btn.danger}>
                {dialog.kind === "reject" ? "거절하기" : dialog.kind === "cancel" ? "취소하기" : "반납 완료"}
              </button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  );
}
