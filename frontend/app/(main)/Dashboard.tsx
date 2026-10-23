"use client";

import Link from "next/link";
import { useUser } from "@/components/AuthProvider";
import { btn, Card, Empty, ErrorState, Loading, OverdueBadge, PageHeader, ReservationBadge } from "@/components/ui";
import { dueText, fmtDateTime, fmtRange } from "@/lib/time";
import type { Reservation } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type UserDash = { role: "user"; renting: Reservation[]; upcoming: Reservation[]; recent: Reservation[] };
type AdminDash = {
  role: "admin";
  counts: { in_use: number; pending: number; overdue: number; return_requested: number; open_reports: number };
  overdue: Reservation[];
  handovers: Reservation[];
  alerts: { reservation: Reservation; blockers: string[] }[];
};

export default function Dashboard() {
  const user = useUser();
  const { data, error, loading, reload } = useLoad<UserDash | AdminDash>("/dashboard");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return null;
  return data.role === "admin" ? <AdminHome d={data} name={user.name} /> : <UserHome d={data} name={user.name} />;
}

function ItemLine({ r }: { r: Reservation }) {
  return (
    <span className="font-semibold">
      {r.item?.name} <span className="font-mono text-sm text-navy-600">{r.item?.asset_code}</span>
    </span>
  );
}

function UserHome({ d, name }: { d: UserDash; name: string }) {
  return (
    <>
      <PageHeader
        title={`${name}님, 안녕하세요`}
        desc="빌린 물품의 반납 기한과 예정된 예약을 확인하세요."
        actions={
          <>
            <Link href="/items" className={btn.primary}>
              물품 찾아 예약하기
            </Link>
            <Link href="/me" className={btn.secondary}>
              나의 예약·대여
            </Link>
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="text-lg font-bold">대여 중인 물품</h2>
          {d.renting.length === 0 ? (
            <p className="mt-3 text-sm text-navy-600">지금 빌리고 있는 물품이 없습니다.</p>
          ) : (
            <ul className="mt-3 grid gap-3">
              {d.renting.map((r) => (
                <li
                  key={r.id}
                  className={`rounded-lg border p-3 ${r.overdue ? "border-rose-300 bg-rose-50" : "border-navy-100"}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <ItemLine r={r} />
                    <ReservationBadge status={r.status} overdue={r.overdue} />
                  </div>
                  <p className={`mt-2 text-sm ${r.overdue ? "font-bold text-rose-800" : "text-navy-700"}`}>
                    반납 기한 {fmtDateTime(r.end_at)} ({dueText(r.end_at)})
                  </p>
                  {r.status === "return_requested" && (
                    <p className="mt-1 text-xs text-navy-600">반납 요청됨 · 관리자가 실물을 확인하면 반납 완료됩니다.</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="text-lg font-bold">예정된 예약</h2>
          {d.upcoming.length === 0 ? (
            <p className="mt-3 text-sm text-navy-600">예정된 예약이 없습니다.</p>
          ) : (
            <ul className="mt-3 grid gap-3">
              {d.upcoming.map((r) => (
                <li key={r.id} className="rounded-lg border border-navy-100 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <ItemLine r={r} />
                    <ReservationBadge status={r.status} />
                  </div>
                  <p className="mt-2 text-sm text-navy-700">{fmtRange(r.start_at, r.end_at)}</p>
                  {r.status === "approved" && (
                    <p className="mt-1 text-xs text-navy-600">예약 확정 · 보관 장소에서 관리자에게 물품을 받으면 대여가 시작됩니다.</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      {d.recent.length > 0 && (
        <Card className="mt-6">
          <h2 className="text-lg font-bold">최근 처리 결과 (7일)</h2>
          <ul className="mt-3 divide-y divide-navy-100">
            {d.recent.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <span>
                  <ItemLine r={r} /> · {fmtRange(r.start_at, r.end_at)}
                  {r.reject_reason && <span className="block text-rose-800">거절 사유: {r.reject_reason}</span>}
                  {r.cancel_reason && <span className="block text-navy-600">취소 사유: {r.cancel_reason}</span>}
                </span>
                <ReservationBadge status={r.status} />
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

function Stat({ label, value, href, tone }: { label: string; value: number; href: string; tone: string }) {
  return (
    <Link href={href} className={`rounded-xl border bg-white p-4 shadow-sm hover:border-teal-500 ${tone}`}>
      <span className="block text-sm font-semibold text-navy-600">{label}</span>
      <span className="mt-1 block text-3xl font-bold tabular-nums">{value}</span>
      <span className="mt-1 block text-xs font-semibold text-teal-800">바로 가기 →</span>
    </Link>
  );
}

function AdminHome({ d, name }: { d: AdminDash; name: string }) {
  const c = d.counts;
  return (
    <>
      <PageHeader
        title="관리자 대시보드"
        desc={`${name}님, 처리해야 할 일을 확인하세요.`}
        actions={
          <>
            <Link href="/admin/reservations?tab=pending" className={btn.primary}>
              승인 대기 처리
            </Link>
            <Link href="/admin/items/new" className={btn.secondary}>
              물품 등록
            </Link>
          </>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="현재 대여 중" value={c.in_use} href="/admin/reservations?tab=renting" tone="border-navy-100" />
        <Stat label="승인 대기" value={c.pending} href="/admin/reservations?tab=pending" tone={c.pending ? "border-amber-300" : "border-navy-100"} />
        <Stat label="연체" value={c.overdue} href="/admin/reservations?tab=overdue" tone={c.overdue ? "border-rose-400 text-rose-800" : "border-navy-100"} />
        <Stat label="반납 확인 대기" value={c.return_requested} href="/admin/reservations?tab=return_requested" tone={c.return_requested ? "border-violet-300" : "border-navy-100"} />
        <Stat label="미처리 고장 신고" value={c.open_reports} href="/admin/reports" tone={c.open_reports ? "border-orange-300" : "border-navy-100"} />
      </div>

      {d.alerts.length > 0 && (
        <section role="alert" className="mt-6 rounded-xl border border-rose-300 bg-rose-50 p-5">
          <h2 className="font-bold text-rose-900">⚠ 인계할 수 없는 확정 예약 ({d.alerts.length})</h2>
          <ul className="mt-3 grid gap-2 text-sm">
            {d.alerts.map((a) => (
              <li key={a.reservation.id} className="rounded-lg bg-white p-3">
                <ItemLine r={a.reservation} /> · {a.reservation.user?.name} · {fmtRange(a.reservation.start_at, a.reservation.end_at)}
                <ul className="mt-1 list-disc pl-5 text-rose-800">
                  {a.blockers.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">연체 중</h2>
            <Link href="/admin/reservations?tab=overdue" className="text-sm font-semibold text-teal-800 underline">
              전체 보기
            </Link>
          </div>
          {d.overdue.length === 0 ? (
            <p className="mt-3 text-sm text-navy-600">연체된 대여가 없습니다.</p>
          ) : (
            <ul className="mt-3 divide-y divide-navy-100">
              {d.overdue.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                  <span>
                    <ItemLine r={r} /> · {r.user?.name}
                    <span className="block font-semibold text-rose-800">
                      기한 {fmtDateTime(r.end_at)} ({dueText(r.end_at)})
                    </span>
                  </span>
                  <OverdueBadge />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">24시간 내 인계 예정</h2>
            <Link href="/admin/reservations?tab=approved" className="text-sm font-semibold text-teal-800 underline">
              전체 보기
            </Link>
          </div>
          {d.handovers.length === 0 ? (
            <Empty title="예정된 인계가 없습니다." />
          ) : (
            <ul className="mt-3 divide-y divide-navy-100">
              {d.handovers.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                  <span>
                    <ItemLine r={r} /> · {r.user?.name}
                    <span className="block text-navy-700">{fmtRange(r.start_at, r.end_at)}</span>
                  </span>
                  <ReservationBadge status={r.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
