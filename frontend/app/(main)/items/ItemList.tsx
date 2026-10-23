"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useUser } from "@/components/AuthProvider";
import ItemThumb from "@/components/ItemThumb";
import PeriodFields, { periodError, type Period } from "@/components/PeriodFields";
import { AvailBadge, btn, Empty, ErrorState, inputCls, ItemBadge, labelCls, Loading, OverdueBadge, PageHeader } from "@/components/ui";
import { defaultSlot, fmtDateTime, toIso } from "@/lib/time";
import type { ItemListRow } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

function RentalState({ row }: { row: ItemListRow }) {
  if (!row.rented) return <span className="text-sm text-navy-600">보관 중</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-sm font-semibold text-navy-800">
      현재 대여 중 · 반납 기한 {row.rented_due && fmtDateTime(row.rented_due)}
      {row.rented_overdue && <OverdueBadge />}
    </span>
  );
}

function PeriodState({ row }: { row: ItemListRow }) {
  if (!row.period) return null;
  return row.period.available ? (
    <AvailBadge ok>선택 기간 예약 가능</AvailBadge>
  ) : (
    <AvailBadge ok={false}>선택 기간 불가 · {row.period.reason}</AvailBadge>
  );
}

export default function ItemList() {
  const user = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const isAdmin = user.role === "admin";

  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const status = params.get("status") ?? "";
  const start = params.get("start");
  const end = params.get("end");
  const availableOnly = params.get("available") === "1";

  const [qInput, setQInput] = useState(q);
  const initial = defaultSlot();
  const fromParam = (iso: string | null, which: "start" | "end") => {
    if (!iso) return null;
    const [d, t] = iso.slice(0, 16).split("T");
    return which === "start" ? { startDate: d, startTime: t } : { endDate: d, endTime: t };
  };
  const [period, setPeriod] = useState<Period>({
    ...initial,
    ...(fromParam(start, "start") ?? {}),
    ...(fromParam(end, "end") ?? {}),
  });
  const [usePeriod, setUsePeriod] = useState(Boolean(start && end));
  const [formError, setFormError] = useState("");

  const qs = new URLSearchParams();
  if (q) qs.set("q", q);
  if (category) qs.set("category", category);
  if (status) qs.set("status", status);
  if (start && end) {
    qs.set("start", start);
    qs.set("end", end);
    if (availableOnly) qs.set("available_only", "true");
  }
  const list = useLoad<{ items: ItemListRow[] }>(`/items?${qs.toString()}`);
  const cats = useLoad<{ categories: string[] }>("/items/categories");

  function apply(e?: React.FormEvent, overrides: Record<string, string | null> = {}) {
    e?.preventDefault();
    setFormError("");
    const next = new URLSearchParams();
    const values: Record<string, string | null> = {
      q: qInput.trim() || null,
      category: category || null,
      status: status || null,
      available: availableOnly ? "1" : null,
      ...overrides,
    };
    if (usePeriod) {
      const err = periodError(period);
      if (err) {
        setFormError(err);
        return;
      }
      values.start = toIso(period.startDate, period.startTime);
      values.end = toIso(period.endDate, period.endTime);
    }
    for (const [k, v] of Object.entries(values)) if (v) next.set(k, v);
    router.replace(`${pathname}?${next.toString()}`);
  }

  const items = list.data?.items ?? [];
  const periodQuery = start && end ? `?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}` : "";

  return (
    <>
      <PageHeader title="물품 찾기" desc="이름이나 관리번호로 찾고, 원하는 사용 기간에 빌릴 수 있는 물품을 확인하세요." />

      <form onSubmit={apply} className="mb-6 grid gap-4 rounded-xl border border-navy-100 bg-white p-4 shadow-sm" role="search">
        <div className="grid gap-3 md:grid-cols-[2fr_1fr_1fr_auto] md:items-end">
          <label className={labelCls}>
            검색어
            <input
              type="search"
              value={qInput}
              onChange={(e) => setQInput(e.target.value)}
              placeholder="예: 마이크, MIC-001"
              className={inputCls}
            />
          </label>
          <label className={labelCls}>
            카테고리
            <select value={category} onChange={(e) => apply(undefined, { category: e.target.value || null })} className={inputCls}>
              <option value="">전체</option>
              {cats.data?.categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className={labelCls}>
            물품 상태
            <select value={status} onChange={(e) => apply(undefined, { status: e.target.value || null })} className={inputCls}>
              <option value="">{isAdmin ? "보관 종료 제외 전체" : "전체"}</option>
              <option value="normal">정상</option>
              <option value="repair">수리 중</option>
              {isAdmin && <option value="retired">보관 종료</option>}
            </select>
          </label>
          <button type="submit" className={btn.primary}>
            검색
          </button>
        </div>

        <div className="rounded-lg bg-navy-50 p-3">
          <label className="flex items-center gap-2 text-sm font-semibold text-navy-800">
            <input type="checkbox" checked={usePeriod} onChange={(e) => setUsePeriod(e.target.checked)} className="size-4 accent-teal-700" />
            사용 기간으로 예약 가능 여부 확인
          </label>
          {usePeriod && (
            <div className="mt-3 grid gap-3">
              <PeriodFields value={period} onChange={setPeriod} idPrefix="search" invalid={!!formError} />
              <div className="flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-2 text-sm text-navy-800">
                  <input
                    type="checkbox"
                    checked={availableOnly}
                    onChange={(e) => apply(undefined, { available: e.target.checked ? "1" : null })}
                    disabled={!(start && end)}
                    className="size-4 accent-teal-700"
                  />
                  예약 가능한 물품만 보기
                </label>
                <button type="submit" className={btn.secondary}>
                  이 기간으로 조회
                </button>
                {start && end && (
                  <button
                    type="button"
                    className="text-sm font-semibold text-navy-700 underline"
                    onClick={() => {
                      setUsePeriod(false);
                      router.replace(pathname + (q ? `?q=${encodeURIComponent(q)}` : ""));
                    }}
                  >
                    기간 조건 지우기
                  </button>
                )}
              </div>
            </div>
          )}
          {formError && (
            <p role="alert" className="mt-2 text-sm font-semibold text-rose-800">
              {formError}
            </p>
          )}
        </div>
      </form>

      {list.loading && !list.data ? (
        <Loading />
      ) : list.error ? (
        <ErrorState message={list.error} onRetry={list.reload} />
      ) : items.length === 0 ? (
        <Empty title="조건에 맞는 물품이 없습니다.">검색어나 필터를 바꿔 보세요.</Empty>
      ) : (
        <>
          <p className="mb-3 text-sm text-navy-600" aria-live="polite">
            {items.length}개 물품
          </p>
          {/* 모바일: 카드 */}
          <ul className="grid gap-3 md:hidden">
            {items.map((row) => (
              <li key={row.id}>
                <Link href={`/items/${row.id}${periodQuery}`} className="flex gap-3 rounded-xl border border-navy-100 bg-white p-3 shadow-sm">
                  <ItemThumb item={row} />
                  <div className="grid min-w-0 gap-1">
                    <span className="font-bold">{row.name}</span>
                    <span className="font-mono text-xs text-navy-600">
                      {row.asset_code} · {row.category}
                    </span>
                    <span className="flex flex-wrap gap-1">
                      <ItemBadge status={row.status} />
                      <PeriodState row={row} />
                    </span>
                    <RentalState row={row} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {/* PC: 표 */}
          <div className="hidden overflow-hidden rounded-xl border border-navy-100 bg-white shadow-sm md:block">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">물품 목록</caption>
              <thead className="bg-navy-50 text-navy-700">
                <tr>
                  <th scope="col" className="px-4 py-3">물품</th>
                  <th scope="col" className="px-4 py-3">카테고리 · 보관 장소</th>
                  <th scope="col" className="px-4 py-3">상태</th>
                  <th scope="col" className="px-4 py-3">현재 대여</th>
                  {start && end && <th scope="col" className="px-4 py-3">선택 기간</th>}
                  <th scope="col" className="px-4 py-3"><span className="sr-only">이동</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-100">
                {items.map((row) => (
                  <tr key={row.id} className="hover:bg-navy-50/50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <ItemThumb item={row} size="sm" />
                        <div>
                          <div className="font-bold">{row.name}</div>
                          <div className="font-mono text-xs text-navy-600">{row.asset_code}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-navy-700">
                      {row.category}
                      <div className="text-xs text-navy-500">{row.location || "-"}</div>
                    </td>
                    <td className="px-4 py-3"><ItemBadge status={row.status} /></td>
                    <td className="px-4 py-3"><RentalState row={row} /></td>
                    {start && end && <td className="px-4 py-3"><PeriodState row={row} /></td>}
                    <td className="px-4 py-3 text-right">
                      <Link href={`/items/${row.id}${periodQuery}`} className={btn.small}>
                        상세·예약
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
