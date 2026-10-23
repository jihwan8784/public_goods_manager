import type { Metadata } from "next";
import NewItem from "./NewItem";

export const metadata: Metadata = { title: "물품 등록" };

export default function Page() {
  return <NewItem />;
}
