import type { Metadata } from "next";
import AdminStudents from "./AdminStudents";

export const metadata: Metadata = { title: "학생 승인" };

export default function Page() {
  return <AdminStudents />;
}
