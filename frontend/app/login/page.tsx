import { Suspense } from "react";
import type { Metadata } from "next";
import LoginForm from "./LoginForm";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "로그인" };

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-50 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <span className="mx-auto grid size-12 place-items-center rounded-xl bg-navy-900 text-2xl text-teal-400" aria-hidden>
            ⇄
          </span>
          <h1 className="mt-3 text-2xl font-bold text-navy-900">public goods manage</h1>
          <p className="mt-1 text-sm text-navy-600">공동 물품 예약·대여 관리</p>
        </div>
        <Suspense fallback={<Loading label="로그인 화면을 준비하는 중…" />}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
