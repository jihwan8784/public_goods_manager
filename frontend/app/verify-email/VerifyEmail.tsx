"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ResendVerification from "@/components/ResendVerification";
import { inputCls, labelCls, Loading } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const [state, setState] = useState<{ kind: "loading" | "ok" | "error"; text?: string }>(
    token ? { kind: "loading" } : { kind: "error", text: "인증 링크가 올바르지 않습니다." },
  );
  const [email, setEmail] = useState("");
  const started = useRef(false);

  useEffect(() => {
    // 링크는 한 번만 쓸 수 있으므로 두 번 호출되지 않게 막는다
    if (!token || started.current) return;
    started.current = true;
    api("/auth/verify-email", { body: { token }, noRedirect: true })
      .then(() => {
        setState({ kind: "ok" });
        setTimeout(() => router.replace("/"), 1500);
      })
      .catch((e) => setState({ kind: "error", text: errorMessage(e) }));
  }, [token, router]);

  if (state.kind === "loading") return <Loading label="인증 링크를 확인하는 중…" />;
  if (state.kind === "ok") {
    return (
      <p role="status" className="rounded-xl border border-teal-300 bg-teal-50 p-5 text-center font-semibold text-teal-900">
        ✔ 이메일 인증이 끝났습니다. 잠시 후 첫 화면으로 이동합니다.
      </p>
    );
  }
  return (
    <div className="grid gap-4 rounded-xl border border-navy-100 bg-white p-6 shadow-sm">
      <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800">
        {state.text}
      </p>
      <label className={labelCls}>
        가입한 이메일
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} autoComplete="email" />
      </label>
      <ResendVerification email={email.trim()} />
    </div>
  );
}
