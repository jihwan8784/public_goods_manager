import { Suspense } from "react";
import type { Metadata } from "next";
import LoginForm from "./LoginForm";
import Logo from "@/components/Logo";
import { Loading } from "@/components/ui";
import { APP_NAME_PARTS, APP_TAGLINE } from "@/lib/brand";

export const metadata: Metadata = { title: "로그인" };

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-50 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <Logo size={56} className="mx-auto" />
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-navy-900">
            {APP_NAME_PARTS[0]}
            <span className="text-teal-700">{APP_NAME_PARTS[1]}</span>
          </h1>
          <p className="mt-1 text-sm text-navy-600">{APP_TAGLINE}</p>
        </div>
        <Suspense fallback={<Loading label="로그인 화면을 준비하는 중…" />}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
