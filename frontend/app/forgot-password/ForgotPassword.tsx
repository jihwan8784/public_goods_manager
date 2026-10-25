"use client";

import { useState } from "react";
import { DevLink } from "@/components/ResendVerification";
import { btn, inputCls, labelCls } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string; devLink?: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^[^@\s]+@[^@\s]+$/.test(email.trim())) {
      setResult({ ok: false, text: "이메일을 정확히 입력해 주세요." });
      return;
    }
    setBusy(true);
    try {
      const r = await api<{ message: string; dev_link?: string }>("/auth/password-reset/request", {
        body: { email: email.trim() },
        noRedirect: true,
      });
      setResult({ ok: true, text: r.message, devLink: r.dev_link });
    } catch (err) {
      setResult({ ok: false, text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-xl border border-navy-100 bg-white p-6 shadow-sm" noValidate>
      <label className={labelCls}>
        가입한 이메일
        <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} />
      </label>
      <div aria-live="polite">
        {result && (
          <p
            role={result.ok ? "status" : "alert"}
            className={`rounded-lg px-3 py-2 text-sm font-semibold ${result.ok ? "bg-teal-50 text-teal-900" : "bg-rose-50 text-rose-800"}`}
          >
            {result.text}
          </p>
        )}
        {result?.devLink && <DevLink href={result.devLink} />}
      </div>
      <button type="submit" disabled={busy} className={btn.primary}>
        {busy ? "보내는 중…" : "재설정 메일 받기"}
      </button>
    </form>
  );
}
