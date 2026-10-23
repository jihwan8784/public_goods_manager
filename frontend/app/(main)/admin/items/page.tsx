import type { Metadata } from "next";
import AdminItems from "./AdminItems";

export const metadata: Metadata = { title: "물품 관리" };

export default function Page() {
  return <AdminItems />;
}
