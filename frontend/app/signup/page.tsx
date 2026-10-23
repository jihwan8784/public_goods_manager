import type { Metadata } from "next";
import Link from "next/link";
import SignupForm from "./SignupForm";

export const metadata: Metadata = { title: "회원가입" };

export default function SignupPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <span className="mx-auto grid size-12 place-items-center rounded-xl bg-navy-900 text-2xl text-teal-400" aria-hidden>
            ⇄
          </span>
          <h1 className="mt-3 text-2xl font-bold text-navy-900">회원가입</h1>
          <p className="mt-1 text-sm text-navy-600">학교·주민센터의 공용 물품을 빌릴 수 있어요.</p>
        </div>
        <SignupForm />
        <p className="mt-4 text-center text-sm text-navy-700">
          이미 계정이 있나요?{" "}
          <Link href="/login" className="font-semibold text-teal-800 underline">
            로그인
          </Link>
        </p>
      </div>
    </main>
  );
}
