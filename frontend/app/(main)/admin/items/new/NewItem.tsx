"use client";

import { BackLink } from "@/components/AppShell";
import { PageHeader } from "@/components/ui";
import { useLoad } from "@/lib/useLoad";
import ItemForm from "../ItemForm";

export default function NewItem() {
  const cats = useLoad<{ categories: string[] }>("/items/categories");
  return (
    <>
      <BackLink href="/admin/items">물품 관리</BackLink>
      <PageHeader title="물품 등록" desc="실물 하나당 하나씩 등록합니다. 사진은 등록 후 올릴 수 있습니다." />
      <ItemForm categories={cats.data?.categories ?? []} />
    </>
  );
}
