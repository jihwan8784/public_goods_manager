"use client";

import Link from "next/link";
import { useState } from "react";
import ItemThumb from "@/components/ItemThumb";
import { AccessBadge, btn, Empty, ErrorState, inputBase, inputCls, ItemBadge, Loading, PageHeader } from "@/components/ui";
import type { ItemFull, ItemStatus } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type Row = ItemFull & { reservation_count: number; rented: boolean; open_reports: number };

export default function AdminItems() {
  const { data, error, loading, reload } = useLoad<{ items: Row[] }>("/admin/items");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"" | ItemStatus>("");
  const [selected, setSelected] = useState<number[]>([]);

  const rows = (data?.items ?? []).filter(
    (i) =>
      (!status || i.status === status) &&
      (!q.trim() ||
        `${i.name} ${i.asset_code} ${i.category} ${i.org?.name ?? ""}`.toLowerCase().includes(q.trim().toLowerCase())),
  );
  const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <>
      <PageHeader
        title="물품 관리"
        desc="관리하는 기관의 물품입니다. 개별 실물마다 관리번호(기관별 고유)를 부여하고, 대여 기록이 있는 물품은 삭제하지 않고 보관 종료로 처리합니다."
        actions={
          <>
            <Link href="/admin/items/new" className={btn.primary}>+ 물품 등록</Link>
            <Link
              href={selected.length ? `/admin/qr?ids=${selected.join(",")}` : "/admin/qr"}
              className={btn.secondary}
            >
              {selected.length ? `선택한 ${selected.length}개 QR 인쇄` : "전체 QR 라벨 인쇄"}
            </Link>
          </>
        }
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="item-q">물품 검색</label>
        <input id="item-q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름, 관리번호, 카테고리, 기관" className={`${inputCls} max-w-xs`} />
        <label className="sr-only" htmlFor="item-status">상태</label>
        <select id="item-status" value={status} onChange={(e) => setStatus(e.target.value as ItemStatus | "")} className={`${inputBase} w-40`}>
          <option value="">모든 상태</option>
          <option value="normal">정상</option>
          <option value="repair">수리 중</option>
          <option value="retired">보관 종료</option>
        </select>
      </div>

      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : rows.length === 0 ? (
        <Empty title={data?.items.length ? "조건에 맞는 물품이 없습니다." : "등록된 물품이 없습니다."}>
          {!data?.items.length && <Link href="/admin/items/new" className="font-semibold text-teal-800 underline">첫 물품 등록하기</Link>}
        </Empty>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-navy-100 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">물품 관리 목록</caption>
            <thead className="bg-navy-50 text-navy-700">
              <tr>
                <th scope="col" className="w-10 px-3 py-3"><span className="sr-only">QR 인쇄 선택</span></th>
                <th scope="col" className="px-3 py-3">물품</th>
                <th scope="col" className="hidden px-3 py-3 md:table-cell">기관 · 보관 장소</th>
                <th scope="col" className="px-3 py-3">상태</th>
                <th scope="col" className="hidden px-3 py-3 sm:table-cell">기록</th>
                <th scope="col" className="px-3 py-3"><span className="sr-only">관리</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-100">
              {rows.map((i) => (
                <tr key={i.id} className={i.status === "retired" ? "text-navy-500" : undefined}>
                  <td className="px-3 py-3">
                    <input type="checkbox" checked={selected.includes(i.id)} onChange={() => toggle(i.id)} aria-label={`${i.asset_code} QR 인쇄 선택`} className="size-4 accent-teal-700" />
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-3">
                      <ItemThumb item={i} size="sm" />
                      <div>
                        <Link href={`/items/${i.id}`} className="font-semibold hover:underline">{i.name}</Link>
                        <div className="font-mono text-xs text-navy-600">{i.asset_code}</div>
                      </div>
                    </div>
                  </td>
                  <td className="hidden px-3 py-3 md:table-cell">
                    {i.org?.name ?? "-"}
                    <div className="text-xs text-navy-500">
                      {i.category} · {i.location || "-"}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1">
                      <ItemBadge status={i.status} />
                      <AccessBadge access={i.access} />
                      {i.rented && <span className="text-xs font-semibold text-teal-800">대여 중</span>}
                    </div>
                    {i.open_reports > 0 && <div className="mt-1 text-xs font-semibold text-orange-800">미처리 신고 {i.open_reports}건</div>}
                  </td>
                  <td className="hidden px-3 py-3 text-navy-600 sm:table-cell">예약 {i.reservation_count}건</td>
                  <td className="px-3 py-3 text-right">
                    <Link href={`/admin/items/${i.id}/edit`} className={btn.small}>수정</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
