"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { BackLink } from "@/components/AppShell";
import { btn, ErrorState, FlashMessage, Loading, PageHeader } from "@/components/ui";
import type { ItemFull } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";
import ItemForm from "../../ItemForm";

type Row = ItemFull & { reservation_count: number; open_reports: number };

export default function EditItem() {
  const { id } = useParams<{ id: string }>();
  const created = useSearchParams().get("created") === "1";
  const list = useLoad<{ items: Row[] }>("/admin/items");
  const cats = useLoad<{ categories: string[] }>("/items/categories");

  if (list.loading && !list.data) return <Loading />;
  if (list.error) return <ErrorState message={list.error} onRetry={list.reload} />;
  const item = list.data?.items.find((i) => String(i.id) === id);
  if (!item) return <ErrorState message="물품을 찾을 수 없습니다." />;

  return (
    <>
      <BackLink href="/admin/items">물품 관리</BackLink>
      <PageHeader
        title={`${item.name} · ${item.asset_code}`}
        desc="물품 정보와 상태를 수정합니다."
        actions={
          <>
            <Link href={`/items/${item.id}`} className={btn.secondary}>상세 화면</Link>
            <Link href={`/admin/qr?ids=${item.id}`} className={btn.secondary}>QR 인쇄</Link>
          </>
        }
      />
      {created && (
        <div className="mb-4">
          <FlashMessage flash={{ kind: "ok", text: "물품을 등록했습니다. 사진을 올리고 QR 라벨을 인쇄해 붙여 주세요." }} />
        </div>
      )}
      <ItemForm
        key={`${item.id}-${item.updated_at}-${item.image_version}`}
        item={item}
        categories={cats.data?.categories ?? []}
        canDelete={item.reservation_count === 0 && item.open_reports === 0}
        onSaved={list.reload}
      />
    </>
  );
}
