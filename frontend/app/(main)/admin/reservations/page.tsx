import { Suspense } from "react";
import type { Metadata } from "next";
import { Loading } from "@/components/ui";
import AdminReservations from "./AdminReservations";

export const metadata: Metadata = { title: "예약·대여 관리" };

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <AdminReservations />
    </Suspense>
  );
}
