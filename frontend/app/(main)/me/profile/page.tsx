import { Suspense } from "react";
import type { Metadata } from "next";
import { Loading } from "@/components/ui";
import Profile from "./Profile";

export const metadata: Metadata = { title: "내 정보" };

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <Profile />
    </Suspense>
  );
}
