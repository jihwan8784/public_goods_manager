import type { Metadata } from "next";
import OrgMap from "./OrgMap";

export const metadata: Metadata = { title: "지도에서 찾기" };

export default function Page() {
  return <OrgMap />;
}
