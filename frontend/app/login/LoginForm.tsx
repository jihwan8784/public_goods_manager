"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { clearCachedUser } from "@/components/AuthProvider";
import ResendVerification from "@/components/ResendVerification";
import { btn, inputCls, labelCls } from "@/components/ui";

const SHOW_DEMO = process.env.NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS === "1";

function safeNext(next: string | null): string {
  // 외부 주소로 보내지 않도록 같은 사이트 경로만 허용
  if (
    next &&
    next.startsWith("/") &&
    !next.startsWith("//") &&
    !next.startsWith("/login")
  )
    return next;
  return "/";
}

export default function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [unverified, setUnverified] = useState(false);
  const [needCode, setNeedCode] = useState(false);
  const [adminCode, setAdminCode] = useState("");
  const [busy, setBusy] = useState(false);
  const verified = params.get("verified") === "1";
  const reset = params.get("reset") === "1";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setUnverified(false);
    if (!email.trim() || !password) {
      setError("아이디와 비밀번호를 모두 입력해 주세요.");
      return;
    }
    if (needCode && !adminCode.trim()) {
      setError("관리자 비밀 코드를 입력해 주세요.");
      return;
    }
    setBusy(true);
    try {
      await api("/auth/login", {
        body: { email, password, admin_code: needCode ? adminCode : undefined },
        noRedirect: true,
      });
      clearCachedUser();
      window.location.assign(safeNext(params.get("next")));
    } catch (err) {
      const code = err instanceof ApiError ? err.code : undefined;
      if (code === "admin_code_required") {
        // 관리자 계정: 비밀 코드 칸을 보여 주고 안내만 한다
        setNeedCode(true);
        setError("");
      } else {
        setError(errorMessage(err));
      }
      if (code === "admin_code_invalid") setAdminCode("");
      setUnverified(code === "email_not_verified");
      setBusy(false);
    }
  }

  function fill(id: string, pw: string) {
    setEmail(id);
    setPassword(pw);
  }

  return (
    <>
      <form
        onSubmit={submit}
        className="grid gap-4 rounded-xl border border-navy-100 bg-white p-6 shadow-sm"
        noValidate
      >
        {reset && (
          <p
            role="status"
            className="rounded-lg bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-900"
          >
            비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요.
          </p>
        )}
        {verified && (
          <p
            role="status"
            className="rounded-lg bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-900"
          >
            이메일 인증이 끝났습니다. 로그인해 주세요.
          </p>
        )}
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
        {needCode && (
          <label className={labelCls}>
            관리자 비밀 코드
            <input
              type="password"
              autoComplete="off"
              value={adminCode}
              onChange={(e) => setAdminCode(e.target.value)}
              className={inputCls}
              aria-describedby="admin-code-help"
              autoFocus
            />
            <span id="admin-code-help" className="text-xs font-normal text-navy-600">
              관리자 계정은 비밀번호와 함께 관리자 비밀 코드가 필요합니다. 5번 틀리면 15분 동안 잠깁니다.
            </span>
          </label>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800"
          >
            {error}
          </p>
        )}
        {unverified && <ResendVerification email={email.trim()} />}
        <button type="submit" disabled={busy} className={btn.primary}>
          {busy ? "로그인 중…" : "로그인"}
        </button>
        <p className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-center text-sm text-navy-700">
          <span>
            처음 오셨나요?{" "}
            <Link
              href="/signup"
              className="font-semibold text-teal-800 underline"
            >
              회원가입
            </Link>
          </span>
          <Link
            href="/forgot-password"
            className="font-semibold text-teal-800 underline"
          >
            비밀번호를 잊으셨나요?
          </Link>
        </p>
        {params.get("next") && (
          <p className="text-center text-xs text-navy-600">
            로그인하면 요청한 화면으로 이동합니다.
          </p>
        )}
      </form>
      {SHOW_DEMO && (
        <section className="mt-4 rounded-xl border border-dashed border-teal-300 bg-teal-50 p-4 text-sm text-navy-800">
          <h2 className="font-bold">개발용 테스트 계정</h2>
          <p className="mt-1 text-xs text-navy-600">
            개발 환경 시연 데이터에만 있는 가상 계정입니다.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className={btn.small}
              onClick={() => fill("admin@pgm.test", "admin1234!")}
            >
              최고 관리자
            </button>
            <button
              type="button"
              className={btn.small}
              onClick={() => fill("gaon.admin@pgm.test", "admin1234!")}
            >
              가온고 관리자
            </button>
            <button
              type="button"
              className={btn.small}
              onClick={() => fill("center.admin@pgm.test", "admin1234!")}
            >
              주민센터 관리자
            </button>
            <button
              type="button"
              className={btn.small}
              onClick={() => fill("student1@pgm.test", "user1234!")}
            >
              가온고 학생(김하늘)
            </button>
            <button
              type="button"
              className={btn.small}
              onClick={() => fill("student3@pgm.test", "user1234!")}
            >
              승인 대기 학생(박솔)
            </button>
            <button
              type="button"
              className={btn.small}
              onClick={() => fill("resident@pgm.test", "user1234!")}
            >
              주민(한결)
            </button>
          </div>
        </section>
      )}
    </>
  );
}
