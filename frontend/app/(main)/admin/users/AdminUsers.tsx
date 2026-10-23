"use client";

import { useState } from "react";
import { useUser } from "@/components/AuthProvider";
import { btn, Card, ErrorState, FlashMessage, inputCls, labelCls, Loading, PageHeader, type Flash } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { Role, User } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

export default function AdminUsers() {
  const me = useUser();
  const list = useLoad<{ users: User[] }>("/admin/users");
  const [form, setForm] = useState({ email: "", name: "", password: "", role: "user" as Role });
  const [flash, setFlash] = useState<Flash>(null);
  const [saving, setSaving] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setFlash(null);
    if (!/^[^@\s]+@[^@\s]+$/.test(form.email)) return setFlash({ kind: "error", text: "아이디는 이메일 형식으로 입력해 주세요." });
    if (!form.name.trim()) return setFlash({ kind: "error", text: "이름을 입력해 주세요." });
    if (form.password.length < 8) return setFlash({ kind: "error", text: "임시 비밀번호는 8자 이상이어야 합니다." });
    setSaving(true);
    try {
      await api("/admin/users", { body: form });
      setFlash({ kind: "ok", text: `${form.name}님 계정을 만들었습니다. 임시 비밀번호를 직접 전달해 주세요.` });
      setForm({ email: "", name: "", password: "", role: "user" });
      list.reload();
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    } finally {
      setSaving(false);
    }
  }

  async function changeRole(u: User, role: Role) {
    setFlash(null);
    try {
      await api(`/admin/users/${u.id}`, { method: "PATCH", body: { role } });
      setFlash({ kind: "ok", text: `${u.name}님의 권한을 ${role === "admin" ? "관리자" : "일반 사용자"}로 바꿨습니다.` });
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
      <PageHeader title="회원 관리" desc="조직 구성원 계정을 만들고 권한을 관리합니다." />
      <div className="mb-4">
        <FlashMessage flash={flash} onClose={() => setFlash(null)} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Card>
          <h2 className="font-bold">계정 목록</h2>
          {list.loading && !list.data ? (
            <Loading />
          ) : list.error ? (
            <ErrorState message={list.error} onRetry={list.reload} />
          ) : (
            <ul className="mt-3 divide-y divide-navy-100">
              {list.data?.users.map((u) => (
                <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                  <span>
                    <span className="font-semibold">{u.name}</span>
                    {u.role === "admin" && <span className="ml-1.5 rounded bg-teal-100 px-1.5 py-0.5 text-xs font-bold text-teal-900">관리자</span>}
                    <span className="block text-xs text-navy-600">{u.email}</span>
                  </span>
                  <span className="flex flex-wrap gap-1.5">
                    <button type="button" className={btn.small} onClick={() => resetPassword(u)}>비밀번호 변경</button>
                    {u.id !== me.id && (
                      <button type="button" className={btn.small} onClick={() => changeRole(u, u.role === "admin" ? "user" : "admin")}>
                        {u.role === "admin" ? "관리자 해제" : "관리자 지정"}
                      </button>
                    )}
                  </span>
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
            <label className={labelCls}>
              권한
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })} className={inputCls}>
                <option value="user">일반 사용자</option>
                <option value="admin">관리자</option>
              </select>
            </label>
            <button type="submit" disabled={saving} className={btn.primary}>{saving ? "만드는 중…" : "계정 만들기"}</button>
          </form>
        </Card>
      </div>
    </>
  );
}
