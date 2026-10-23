import { Suspense } from "react";
import { Loading } from "@/components/ui";
import ItemDetail from "./ItemDetail";

export default function ItemDetailPage() {
  return (
    <Suspense fallback={<Loading />}>
      <ItemDetail />
    </Suspense>
  );
}
