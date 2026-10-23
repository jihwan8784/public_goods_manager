import type { Metadata } from "next";
import AdminOrgs from "./AdminOrgs";

export const metadata: Metadata = { title: "기관 관리" };

export default function Page() {
  return <AdminOrgs />;
}
