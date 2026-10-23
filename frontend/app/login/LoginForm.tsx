"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { btn, inputCls, labelCls } from "@/components/ui";

const SHOW_DEMO = process.env.NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS === "1";

function safeNext(next: string | null): string {
  // 외부 주소로 보내지 않도록 같은 사이트 경로만 허용
  if (next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login")) return next;
  return "/";
}

export default function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("아이디와 비밀번호를 모두 입력해 주세요.");
      return;
    }
    setBusy(true);
    try {
      await api("/auth/login", { body: { email, password }, noRedirect: true });
      window.location.assign(safeNext(params.get("next")));
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  function fill(id: string, pw: string) {
    setEmail(id);
    setPassword(pw);
  }

  return (
    <>
      <form onSubmit={submit} className="grid gap-4 rounded-xl border border-navy-100 bg-white p-6 shadow-sm" noValidate>
        <label className={labelCls}>
          아이디 (이메일)
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls}
            aria-invalid={!!error}
            required
          />
        </label>
        <label className={labelCls}>
          비밀번호
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputCls}
            aria-invalid={!!error}
            required
          />
        </label>
        {error && (
          <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className={btn.primary}>
          {busy ? "로그인 중…" : "로그인"}
        </button>
        <p className="text-center text-sm text-navy-700">
          처음 오셨나요?{" "}
          <Link href="/signup" className="font-semibold text-teal-800 underline">
            회원가입
          </Link>
        </p>
        {params.get("next") && (
          <p className="text-center text-xs text-navy-600">로그인하면 요청한 화면으로 이동합니다.</p>
        )}
      </form>
      {SHOW_DEMO && (
        <section className="mt-4 rounded-xl border border-dashed border-teal-300 bg-teal-50 p-4 text-sm text-navy-800">
          <h2 className="font-bold">개발용 테스트 계정</h2>
          <p className="mt-1 text-xs text-navy-600">개발 환경 시연 데이터에만 있는 가상 계정입니다.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className={btn.small} onClick={() => fill("admin@pgm.test", "admin1234!")}>
              서비스 관리자
            </button>
            <button type="button" className={btn.small} onClick={() => fill("gaon.admin@pgm.test", "admin1234!")}>
              가온고 관리자
            </button>
            <button type="button" className={btn.small} onClick={() => fill("center.admin@pgm.test", "admin1234!")}>
              주민센터 관리자
            </button>
            <button type="button" className={btn.small} onClick={() => fill("student1@pgm.test", "user1234!")}>
              가온고 학생(김하늘)
            </button>
            <button type="button" className={btn.small} onClick={() => fill("student3@pgm.test", "user1234!")}>
              승인 대기 학생(박솔)
            </button>
            <button type="button" className={btn.small} onClick={() => fill("resident@pgm.test", "user1234!")}>
              주민(한결)
            </button>
          </div>
        </section>
      )}
    </>
  );
}
