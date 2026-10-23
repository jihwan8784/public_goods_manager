import type { Metadata } from "next";
import AdminUsers from "./AdminUsers";

export const metadata: Metadata = { title: "회원 관리" };

export default function Page() {
  return <AdminUsers />;
}
