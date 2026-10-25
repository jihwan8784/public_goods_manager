"use client";

import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { btn } from "./ui";

/** 인증 메일 다시 보내기 버튼 (서버가 60초에 한 번으로 제한) */
export default function ResendVerification({ email }: { email: string }) {
  const [state, setState] = useState<{ kind: "idle" | "busy" | "ok" | "error"; text?: string; devLink?: string }>({
    kind: "idle",
  });

  async function resend() {
    setState({ kind: "busy" });
    try {
      const r = await api<{ message: string; dev_link?: string }>("/auth/resend-verification", {
        body: { email },
        noRedirect: true,
      });
      setState({ kind: "ok", text: r.message, devLink: r.dev_link });
    } catch (e) {
      setState({ kind: "error", text: errorMessage(e) });
    }
  }

  return (
    <div className="grid gap-2">
      <button type="button" className={btn.secondary} onClick={resend} disabled={state.kind === "busy" || !email}>
        {state.kind === "busy" ? "보내는 중…" : "인증 메일 다시 보내기"}
      </button>
      <div aria-live="polite" className="text-sm">
        {state.kind === "ok" && <p className="font-semibold text-teal-900">{state.text}</p>}
        {state.kind === "error" && <p className="font-semibold text-rose-800">{state.text}</p>}
        {state.devLink && <DevLink href={state.devLink} />}
      </div>
    </div>
  );
}

/** 메일 발송 설정이 없는 개발 환경에서만 서버가 링크를 돌려준다 */
export function DevLink({ href }: { href: string }) {
  return (
    <p className="mt-1 rounded-md border border-dashed border-amber-400 bg-amber-50 p-2 text-xs text-amber-950">
      [개발 환경] 메일 발송 설정이 없어 실제 메일은 보내지 않았습니다.{" "}
      <a href={href} className="font-semibold underline">
        여기를 눌러 인증 링크 열기
      </a>
    </p>
  );
}
