import { Suspense } from "react";
import type { Metadata } from "next";
import AuthCard from "@/components/AuthCard";
import { Loading } from "@/components/ui";
import VerifyEmail from "./VerifyEmail";

export const metadata: Metadata = { title: "이메일 인증" };

export default function Page() {
  return (
    <AuthCard title="이메일 인증">
      <Suspense fallback={<Loading label="인증 링크를 확인하는 중…" />}>
        <VerifyEmail />
      </Suspense>
    </AuthCard>
  );
}
