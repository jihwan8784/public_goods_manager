import Link from "next/link";
import type { ReactNode } from "react";
import Logo from "./Logo";

/** 로그인 전 화면(인증·비밀번호 찾기 등)의 공통 틀 */
export default function AuthCard({ title, desc, children }: { title: string; desc?: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-50 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <Logo size={56} className="mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-navy-900">{title}</h1>
          {desc && <p className="mt-1 text-sm text-navy-600">{desc}</p>}
        </div>
        {children}
        <p className="mt-4 text-center text-sm">
          <Link href="/login" className="font-semibold text-teal-800 underline">
            로그인 화면으로
          </Link>
        </p>
      </div>
    </main>
  );
}
