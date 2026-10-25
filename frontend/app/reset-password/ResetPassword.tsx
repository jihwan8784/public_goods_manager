"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { btn, inputCls, labelCls } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function ResetPassword() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (pw.length < 8) return setError("비밀번호는 8자 이상이어야 합니다.");
    if (pw !== pw2) return setError("비밀번호가 서로 다릅니다.");
    setBusy(true);
    try {
      await api("/auth/password-reset/confirm", { body: { token, password: pw }, noRedirect: true });
      router.replace("/login?reset=1");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <p role="alert" className="rounded-xl bg-rose-50 p-4 text-sm font-semibold text-rose-800">
        링크가 올바르지 않습니다.{" "}
        <Link href="/forgot-password" className="underline">
          재설정 메일을 다시 받아 주세요.
        </Link>
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-xl border border-navy-100 bg-white p-6 shadow-sm" noValidate>
      <label className={labelCls}>
        새 비밀번호 (8자 이상)
        <input type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} className={inputCls} aria-invalid={!!error} />
      </label>
      <label className={labelCls}>
        새 비밀번호 확인
        <input type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} className={inputCls} aria-invalid={!!error} />
      </label>
      {error && (
        <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800">
          {error}{" "}
          {error.includes("링크") && (
            <Link href="/forgot-password" className="underline">
              다시 요청하기
            </Link>
          )}
        </p>
      )}
      <button type="submit" disabled={busy} className={btn.primary}>
        {busy ? "바꾸는 중…" : "비밀번호 바꾸기"}
      </button>
    </form>
  );
}
