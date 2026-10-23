import { Suspense } from "react";
import type { Metadata } from "next";
import { Loading } from "@/components/ui";
import QrLabels from "./QrLabels";

export const metadata: Metadata = { title: "QR 라벨 인쇄" };

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <QrLabels />
    </Suspense>
  );
}
