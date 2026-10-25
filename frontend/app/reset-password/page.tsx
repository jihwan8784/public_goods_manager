import { Suspense } from "react";
import type { Metadata } from "next";
import AuthCard from "@/components/AuthCard";
import { Loading } from "@/components/ui";
import ResetPassword from "./ResetPassword";

export const metadata: Metadata = { title: "새 비밀번호" };

export default function Page() {
  return (
    <AuthCard title="새 비밀번호 정하기">
      <Suspense fallback={<Loading />}>
        <ResetPassword />
      </Suspense>
    </AuthCard>
  );
}
