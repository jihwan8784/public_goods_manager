import type { Metadata } from "next";
import AuthCard from "@/components/AuthCard";
import ForgotPassword from "./ForgotPassword";

export const metadata: Metadata = { title: "비밀번호 찾기" };

export default function Page() {
  return (
    <AuthCard title="비밀번호 찾기" desc="가입한 이메일로 비밀번호를 다시 정하는 링크를 보내 드립니다.">
      <ForgotPassword />
    </AuthCard>
  );
}
