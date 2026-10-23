import { Suspense } from "react";
import { Loading } from "@/components/ui";
import EditItem from "./EditItem";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <EditItem />
    </Suspense>
  );
}
