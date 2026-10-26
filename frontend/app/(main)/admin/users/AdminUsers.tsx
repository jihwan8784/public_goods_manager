"use client";

import { useState } from "react";
import Dialog from "@/components/Dialog";
import OrgPicker from "@/components/OrgPicker";
import { btn, Card, ErrorState, FlashMessage, inputCls, labelCls, Loading, PageHeader, type Flash } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { OrgBrief, Role } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type User = {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_student: boolean;
  student_status: string;
  school: OrgBrief | null;
  managed_orgs: OrgBrief[];
  email_verified: boolean;
};
type PickedOrg = OrgBrief & { address: string };

export default function AdminUsers() {
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const list = useLoad<{ users: User[] }>(`/admin/users${applied ? `?q=${encodeURIComponent(applied)}` : ""}`);
  const [form, setForm] = useState({ email: "", name: "", password: "" });
  const [formOrg, setFormOrg] = useState<PickedOrg | null>(null);
  const [flash, setFlash] = useState<Flash>(null);
  const [saving, setSaving] = useState(false);
  const [assignFor, setAssignFor] = useState<User | null>(null);
  const [assignOrg, setAssignOrg] = useState<PickedOrg | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setFlash(null);
    if (!/^[^@\s]+@[^@\s]+$/.test(form.email)) return setFlash({ kind: "error", text: "아이디는 이메일 형식으로 입력해 주세요." });
    if (!form.name.trim()) return setFlash({ kind: "error", text: "이름을 입력해 주세요." });
    if (form.password.length < 8) return setFlash({ kind: "error", text: "임시 비밀번호는 8자 이상이어야 합니다." });
    setSaving(true);
    try {
      await api("/admin/users", { body: { ...form, org_id: formOrg?.id ?? null } });
      setFlash({
        kind: "ok",
        text: formOrg
          ? `${form.name}님 계정을 ${formOrg.name} 관리자로 만들었습니다. 임시 비밀번호와 관리자 비밀 코드를 직접 전달해 주세요.`
          : `${form.name}님 계정을 만들었습니다. 임시 비밀번호를 직접 전달해 주세요.`,
      });
      setForm({ email: "", name: "", password: "" });
      setFormOrg(null);
      list.reload();
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    } finally {
      setSaving(false);
    }
  }

  async function assign() {
    if (!assignFor || !assignOrg) return;
    try {
      await api(`/admin/orgs/${assignOrg.id}/admins`, { body: { email: assignFor.email } });
      setFlash({ kind: "ok", text: `${assignFor.name}님을 ${assignOrg.name} 관리자로 지정했습니다.` });
      setAssignFor(null);
      setAssignOrg(null);
      list.reload();
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    }
  }

  async function unassign(u: User, org: OrgBrief) {
    if (!window.confirm(`${u.name}님의 ${org.name} 관리자 권한을 해제할까요?`)) return;
    try {
      await api(`/admin/orgs/${org.id}/admins/${u.id}`, { method: "DELETE" });
      setFlash({ kind: "ok", text: `${u.name}님의 ${org.name} 관리자 권한을 해제했습니다.` });
      list.reload();
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    }
  }

  async function markVerified(u: User) {
    if (!window.confirm(`${u.name}(${u.email})님의 이메일을 인증된 것으로 처리할까요? 본인 확인을 한 경우에만 사용하세요.`)) return;
    try {
      await api(`/admin/users/${u.id}`, { method: "PATCH", body: { verify_email: true } });
      setFlash({ kind: "ok", text: `${u.name}님을 이메일 인증 처리했습니다. 이제 로그인할 수 있습니다.` });
      list.reload();
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    }
  }

  async function resetPassword(u: User) {
    const pw = window.prompt(`${u.name}님의 새 임시 비밀번호 (8자 이상)`);
    if (pw === null) return;
    if (pw.length < 8) return setFlash({ kind: "error", text: "비밀번호는 8자 이상이어야 합니다." });
    try {
      await api(`/admin/users/${u.id}`, { method: "PATCH", body: { password: pw } });
      setFlash({ kind: "ok", text: `${u.name}님의 비밀번호를 바꿨습니다.` });
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    }
  }

  return (
    <>
      <PageHeader
        title="회원 관리"
        desc="관리자 권한은 기관을 정해서 줍니다. 기관 관리자는 자기 기관의 물품·예약·학생 승인만 관리합니다. 최고 관리자 권한은 화면에서 줄 수 없습니다."
      />
      <div className="mb-4">
        <FlashMessage flash={flash} onClose={() => setFlash(null)} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Card>
          <h2 className="font-bold">계정 목록</h2>
          <form
            role="search"
            className="mt-2 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setApplied(q.trim());
            }}
          >
            <label className="sr-only" htmlFor="user-q">이름 또는 이메일 검색</label>
            <input id="user-q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름 또는 이메일" className={inputCls} />
            <button type="submit" className={btn.secondary}>검색</button>
          </form>
          {list.loading && !list.data ? (
            <Loading />
          ) : list.error ? (
            <ErrorState message={list.error} onRetry={list.reload} />
          ) : (
            <ul className="mt-3 divide-y divide-navy-100">
              {list.data?.users.map((u) => (
                <li key={u.id} className="grid gap-2 py-3 text-sm">
                  <div>
                    <span className="font-semibold">{u.name}</span>
                    {u.role === "admin" && (
                      <span className="ml-1.5 rounded bg-navy-900 px-1.5 py-0.5 text-xs font-bold text-white">최고 관리자</span>
                    )}
                    {u.role !== "admin" && u.managed_orgs.length > 0 && (
                      <span className="ml-1.5 rounded bg-teal-100 px-1.5 py-0.5 text-xs font-bold text-teal-900">기관 관리자</span>
                    )}
                    <span className="block text-xs text-navy-600">
                      {u.email}
                      {!u.email_verified && <span className="ml-1 font-semibold text-amber-800">· 이메일 미인증</span>}
                    </span>
                    {u.school && (
                      <span className="block text-xs text-indigo-900">
                        🎓 {u.school.name} ({u.student_status === "approved" ? "승인" : u.student_status === "pending" ? "승인 대기" : "거절"})
                      </span>
                    )}
                  </div>
                  {u.managed_orgs.length > 0 && (
                    <ul className="flex flex-wrap gap-1.5">
                      {u.managed_orgs.map((o) => (
                        <li key={o.id} className="inline-flex items-center gap-1 rounded-full border border-teal-300 bg-teal-50 px-2 py-0.5 text-xs text-teal-900">
                          {o.name}
                          <button
                            type="button"
                            className="font-bold text-rose-800"
                            aria-label={`${o.name} 관리자 권한 해제`}
                            onClick={() => unassign(u, o)}
                          >
                            ✕
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    {u.role !== "admin" && (
                      <button
                        type="button"
                        className={btn.small}
                        onClick={() => {
                          setAssignOrg(null);
                          setAssignFor(u);
                        }}
                      >
                        기관 관리자 지정
                      </button>
                    )}
                    {!u.email_verified && (
                      <button type="button" className={btn.small} onClick={() => markVerified(u)}>
                        이메일 인증 처리
                      </button>
                    )}
                    <button type="button" className={btn.small} onClick={() => resetPassword(u)}>비밀번호 변경</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="content-start">
          <h2 className="font-bold">새 계정 만들기</h2>
          <form onSubmit={create} className="mt-3 grid gap-3" noValidate>
            <label className={labelCls}>
              아이디 (이메일)
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputCls} autoComplete="off" required />
            </label>
            <label className={labelCls}>
              이름
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={50} className={inputCls} required />
            </label>
            <label className={labelCls}>
              임시 비밀번호 (8자 이상)
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputCls} autoComplete="new-password" required />
            </label>
            <OrgPicker
              label="관리할 기관 (선택 — 비우면 일반 회원)"
              value={formOrg}
              onChange={setFormOrg}
              placeholder="기관 이름으로 검색 (학교·주민센터)"
            />
            <button type="submit" disabled={saving} className={btn.primary}>{saving ? "만드는 중…" : "계정 만들기"}</button>
          </form>
        </Card>
      </div>

      <Dialog open={!!assignFor} title="기관 관리자 지정" onClose={() => setAssignFor(null)}>
        {assignFor && (
          <div className="grid gap-4">
            <p className="text-sm">
              <strong>{assignFor.name}</strong> ({assignFor.email})님에게 관리 권한을 줄 기관을 고르세요.
            </p>
            <OrgPicker label="기관" value={assignOrg} onChange={setAssignOrg} placeholder="기관 이름으로 검색 (학교·주민센터)" />
            <div className="flex justify-end gap-2">
              <button type="button" className={btn.secondary} onClick={() => setAssignFor(null)}>닫기</button>
              <button type="button" className={btn.primary} disabled={!assignOrg} onClick={assign}>지정하기</button>
            </div>
          </div>
        )}
      </Dialog>
    </>
  );
}
