import { Suspense } from "react";
import type { Metadata } from "next";
import { Loading } from "@/components/ui";
import ItemList from "./ItemList";

export const metadata: Metadata = { title: "물품 찾기" };

export default function ItemsPage() {
  return (
    <Suspense fallback={<Loading />}>
      <ItemList />
    </Suspense>
  );
}
