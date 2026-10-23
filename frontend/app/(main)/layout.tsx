import { Suspense } from "react";
import AppShell from "@/components/AppShell";
import { Loading } from "@/components/ui";

export default function MainLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4">
          <Loading />
        </div>
      }
    >
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
