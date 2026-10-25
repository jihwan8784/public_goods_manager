"use client";

import { useState } from "react";
import Dialog from "@/components/Dialog";
import { btn, Empty, ErrorState, FlashMessage, inputCls, labelCls, LiveBadge, Loading, PageHeader, type Flash } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { fmtDateTime } from "@/lib/time";
import type { OrgBrief, StudentStatus } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type Student = {
  id: number;
  name: string;
  email: string;
  student_no: string | null;
  status: StudentStatus;
  status_label: string;
  reject_reason: string | null;
  school: OrgBrief | null;
  created_at: string;
  reviewed_at: string | null;
  birth_date: string | null;
  age: number | null;
  email_verified: boolean;
};

const TABS = [
  ["pending", "승인 대기"],
  ["approved", "승인됨"],
  ["rejected", "거절됨"],
  ["all", "전체"],
] as const;

const TONE: Record<StudentStatus, string> = {
  none: "bg-slate-100 text-slate-700",
  pending: "bg-amber-50 text-amber-900 ring-1 ring-amber-300",
  approved: "bg-teal-50 text-teal-900 ring-1 ring-teal-300",
  rejected: "bg-rose-50 text-rose-900 ring-1 ring-rose-300",
};

export default function AdminStudents() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("pending");
  const list = useLoad<{ students: Student[] }>(`/admin/students?status=${tab}`, { refreshMs: 20000 });
  const [flash, setFlash] = useState<Flash>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState<Student | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");

  async function approve(s: Student) {
    setBusyId(s.id);
    try {
      await api(`/admin/students/${s.id}/approve`, { method: "POST" });
      setFlash({ kind: "ok", text: `${s.name} 학생을 승인했습니다. 이제 ${s.school?.name} 물품을 빌릴 수 있습니다.` });
      list.reload();
    } catch (e) {
      setFlash({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusyId(null);
    }
  }

  async function reject() {
    if (!rejecting) return;
    if (!reason.trim()) return setReasonError("거절 사유를 입력해 주세요. 학생에게 표시됩니다.");
    setBusyId(rejecting.id);
    try {
      await api(`/admin/students/${rejecting.id}/reject`, { body: { reason } });
      setFlash({ kind: "ok", text: `${rejecting.name} 학생 인증을 거절했습니다.` });
      setRejecting(null);
      list.reload();
    } catch (e) {
      setReasonError(errorMessage(e));
    } finally {
      setBusyId(null);
    }
  }

  const rows = list.data?.students ?? [];

  return (
    <>
      <PageHeader
        title="학생 승인"
        desc="관리하는 학교로 가입 신청한 학생입니다. 학번·이름을 학교 명부와 대조한 뒤 승인하세요. 승인된 학생만 학교 전용 물품을 빌릴 수 있습니다."
        actions={<LiveBadge updatedAt={list.updatedAt} />}
      />
      <div role="tablist" aria-label="승인 상태" className="mb-4 flex gap-1 overflow-x-auto pb-1">
        {TABS.map(([k, label]) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={tab === k}
            onClick={() => setTab(k)}
            className={`shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-semibold ${
              tab === k ? "border-navy-900 bg-navy-900 text-white" : "border-navy-200 bg-white text-navy-700 hover:bg-navy-50"
            }`}
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
        <Empty title={tab === "pending" ? "승인을 기다리는 학생이 없습니다." : "해당하는 학생이 없습니다."} />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {rows.map((s) => (
            <li key={s.id} className="rounded-xl border border-navy-100 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-bold">
                    {s.name} <span className="font-normal text-navy-600">· 학번 {s.student_no}</span>
                  </p>
                  <p className="text-sm text-navy-700">
                    {s.school?.name}
                    {s.birth_date && (
                      <span className="text-navy-600">
                        {" "}
                        · {s.birth_date} (만 {s.age}세)
                      </span>
                    )}
                  </p>
                  <p className="break-all text-xs text-navy-500">
                    {s.email} · {fmtDateTime(s.created_at)} 가입
                    {!s.email_verified && <span className="ml-1 font-semibold text-amber-800">· 이메일 미인증</span>}
                  </p>
                </div>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${TONE[s.status]}`}>{s.status_label}</span>
              </div>
              {s.reject_reason && <p className="mt-2 text-sm text-rose-800">거절 사유: {s.reject_reason}</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                {s.status !== "approved" && (
                  <button type="button" className={btn.primary} disabled={busyId === s.id} onClick={() => approve(s)}>
                    학생 승인
                  </button>
                )}
                {s.status !== "rejected" && (
                  <button
                    type="button"
                    className={btn.danger}
                    disabled={busyId === s.id}
                    onClick={() => {
                      setReason("");
                      setReasonError("");
                      setRejecting(s);
                    }}
                  >
                    {s.status === "approved" ? "승인 취소(거절)" : "거절"}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <Dialog open={!!rejecting} title="학생 인증 거절" onClose={() => setRejecting(null)}>
        {rejecting && (
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              reject();
            }}
          >
            <p className="text-sm">
              <strong>{rejecting.name}</strong> ({rejecting.school?.name}, 학번 {rejecting.student_no})
            </p>
            <label className={labelCls}>
              거절 사유 (학생에게 표시됨)
              <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} className={inputCls} aria-invalid={!!reasonError} />
            </label>
            {reasonError && <p role="alert" className="text-sm font-semibold text-rose-800">{reasonError}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" className={btn.secondary} onClick={() => setRejecting(null)}>
                닫기
              </button>
              <button type="submit" className={btn.danger} disabled={busyId === rejecting.id}>
                거절하기
              </button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  );
}
