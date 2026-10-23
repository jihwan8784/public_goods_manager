"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useAuth, useUser } from "@/components/AuthProvider";
import OrgPicker from "@/components/OrgPicker";
import { btn, Card, FlashMessage, inputCls, labelCls, PageHeader, type Flash } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { ORG_KIND_LABEL } from "@/lib/labels";
import type { OrgBrief, StudentStatus } from "@/lib/types";

const STATUS_TONE: Record<StudentStatus, string> = {
  none: "bg-slate-100 text-slate-800",
  pending: "bg-amber-50 text-amber-900 ring-1 ring-amber-300",
  approved: "bg-teal-50 text-teal-900 ring-1 ring-teal-300",
  rejected: "bg-rose-50 text-rose-900 ring-1 ring-rose-300",
};

export default function Profile() {
  const user = useUser();
  const { refresh } = useAuth();
  const welcome = useSearchParams().get("welcome") === "student";
  const st = user.student;
  const [editing, setEditing] = useState(!st.is_student);
  const [school, setSchool] = useState<(OrgBrief & { address: string }) | null>(null);
  const [studentNo, setStudentNo] = useState(st.student_no ?? "");
  const [flash, setFlash] = useState<Flash>(
    welcome ? { kind: "ok", text: "가입을 환영합니다! 학교 관리자가 학생 인증을 승인하면 학교 물품을 빌릴 수 있어요." } : null,
  );
  const [busy, setBusy] = useState(false);

  async function apply(e: React.FormEvent) {
    e.preventDefault();
    if (!school) return setFlash({ kind: "error", text: "학교를 검색해서 선택해 주세요." });
    if (!studentNo.trim()) return setFlash({ kind: "error", text: "학번을 입력해 주세요." });
    setBusy(true);
    try {
      await api("/me/student", { method: "PUT", body: { school_id: school.id, student_no: studentNo.trim() } });
      await refresh();
      setEditing(false);
      setFlash({ kind: "ok", text: `${school.name} 학생 인증을 신청했습니다. 학교 관리자의 승인을 기다려 주세요.` });
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    if (!window.confirm("학생 인증을 해제할까요? 학교 전용 물품은 더 이상 빌릴 수 없습니다.")) return;
    try {
      await api("/me/student", { method: "DELETE" });
      await refresh();
      setEditing(true);
      setFlash({ kind: "ok", text: "학생 인증을 해제했습니다." });
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    }
  }

  return (
    <>
      <PageHeader title="내 정보" desc="계정과 학생 인증 상태를 확인합니다." />
      <div className="mb-4">
        <FlashMessage flash={flash} onClose={() => setFlash(null)} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="font-bold">계정</h2>
          <dl className="mt-3 grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
            <dt className="font-semibold text-navy-600">이름</dt>
            <dd>{user.name}</dd>
            <dt className="font-semibold text-navy-600">아이디</dt>
            <dd className="break-all">{user.email}</dd>
            <dt className="font-semibold text-navy-600">권한</dt>
            <dd>{user.role === "admin" ? "서비스 관리자" : user.is_staff ? "기관 관리자" : "일반 회원"}</dd>
          </dl>
          {user.managed_orgs.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-bold text-navy-700">관리하는 기관</h3>
              <ul className="mt-1 grid gap-1 text-sm">
                {user.managed_orgs.map((o) => (
                  <li key={o.id}>
                    {o.name} <span className="text-xs text-navy-600">({ORG_KIND_LABEL[o.kind]})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card>
          <h2 className="font-bold">학생 인증</h2>
          {st.is_student && (
            <div className="mt-3 grid gap-2 text-sm">
              <p>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${STATUS_TONE[st.status]}`}>{st.status_label}</span>
              </p>
              <p>
                <span className="font-semibold">{st.school?.name}</span> · 학번 {st.student_no}
              </p>
              {st.status === "pending" && <p className="text-navy-700">학교 관리자가 확인하면 승인됩니다. 승인 전에는 누구나 빌릴 수 있는 물품만 이용할 수 있어요.</p>}
              {st.status === "approved" && (
                <p className="text-navy-700">
                  {st.school?.name}의 소속 학생 전용 물품을 빌릴 수 있습니다.{" "}
                  <Link href={`/items?org=${st.school?.id}`} className="font-semibold text-teal-800 underline">
                    우리 학교 물품 보기
                  </Link>
                </p>
              )}
              {st.status === "rejected" && (
                <p className="font-semibold text-rose-800">거절 사유: {st.reject_reason ?? "-"} — 정보를 고쳐 다시 신청해 주세요.</p>
              )}
              {!editing && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <button type="button" className={btn.secondary} onClick={() => setEditing(true)}>
                    {st.status === "rejected" ? "다시 신청" : "학교·학번 변경"}
                  </button>
                  <button type="button" className={btn.danger} onClick={withdraw}>
                    학생 인증 해제
                  </button>
                </div>
              )}
            </div>
          )}
          {!st.is_student && !editing && <p className="mt-3 text-sm text-navy-700">학생 인증을 하지 않았습니다.</p>}
          {editing && (
            <form onSubmit={apply} className="mt-3 grid gap-3" noValidate>
              <p className="text-sm text-navy-700">
                {st.is_student ? "학교나 학번을 바꾸면 다시 승인을 받아야 합니다." : "학생이라면 학교를 선택해 인증을 신청하세요. 승인되면 학교 물품을 빌릴 수 있어요."}
              </p>
              <OrgPicker label="다니는 학교" kind="school" value={school} onChange={setSchool} />
              <label className={labelCls}>
                학번 (또는 학년·반·번호)
                <input value={studentNo} onChange={(e) => setStudentNo(e.target.value)} maxLength={40} className={inputCls} />
              </label>
              <div className="flex gap-2">
                <button type="submit" disabled={busy} className={btn.primary}>
                  {busy ? "신청 중…" : "학생 인증 신청"}
                </button>
                {st.is_student && (
                  <button type="button" className={btn.secondary} onClick={() => setEditing(false)}>
                    취소
                  </button>
                )}
              </div>
            </form>
          )}
        </Card>
      </div>
    </>
  );
}
