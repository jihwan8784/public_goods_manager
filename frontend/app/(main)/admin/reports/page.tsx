import type { Metadata } from "next";
import AdminReports from "./AdminReports";

export const metadata: Metadata = { title: "고장 신고 관리" };

export default function Page() {
  return <AdminReports />;
}
