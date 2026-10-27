"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BackLink } from "@/components/AppShell";
import { btn, Empty, ErrorState, Loading, PageHeader } from "@/components/ui";
import { itemUrl, qrSvg } from "@/lib/qr";
import type { ItemFull } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";
import { APP_NAME } from "@/lib/brand";

export default function QrLabels() {
  const idsParam = useSearchParams().get("ids") ?? "";
  // 선택한 물품만, 없으면 보관 종료가 아닌 물품을 앞에서부터 최대 200개
  const { data, error, loading, reload } = useLoad<{ items: ItemFull[] }>(
    idsParam ? `/admin/items?ids=${encodeURIComponent(idsParam)}&limit=500` : "/admin/items?limit=200",
  );
  const [svgs, setSvgs] = useState<Record<number, string>>({});

  const items = (data?.items ?? []).filter((i) => (idsParam ? true : i.status !== "retired"));
  const key = items.map((i) => i.id).join(",");

  useEffect(() => {
    let alive = true;
    const list = key ? key.split(",").map(Number) : [];
    Promise.all(list.map(async (id) => [id, await qrSvg(itemUrl(id))] as const)).then((pairs) => {
      if (alive) setSvgs(Object.fromEntries(pairs));
    });
    return () => {
      alive = false;
    };
  }, [key]);

  if (loading && !data) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={reload} />;

  return (
    <>
      <div className="no-print">
        <BackLink href="/admin/items">물품 관리</BackLink>
        <PageHeader
          title="QR 라벨 인쇄"
          desc={`${items.length}개 라벨 · 휴대전화 카메라로 찍으면 물품 상세 페이지가 열립니다.`}
          actions={
            <button type="button" className={btn.primary} onClick={() => window.print()} disabled={!items.length}>
              인쇄하기
            </button>
          }
        />
      </div>
      {items.length === 0 ? (
        <Empty title="인쇄할 물품이 없습니다." />
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 print:grid-cols-3">
          {items.map((i) => (
            <li key={i.id} className="print-break-avoid rounded-lg border-2 border-dashed border-navy-300 bg-white p-3 text-center">
              <div
                className="mx-auto w-32"
                role="img"
                aria-label={`${i.asset_code} QR 코드`}
                dangerouslySetInnerHTML={{ __html: svgs[i.id] ?? "" }}
              />
              <p className="mt-1 font-mono text-lg font-bold">{i.asset_code}</p>
              <p className="text-sm">{i.name}</p>
              <p className="text-xs text-navy-600">{APP_NAME}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
