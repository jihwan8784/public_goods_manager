"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useUser } from "@/components/AuthProvider";
import { BackLink } from "@/components/AppShell";
import ItemThumb from "@/components/ItemThumb";
import PeriodFields, { periodError, type Period } from "@/components/PeriodFields";
import QrPanel from "@/components/QrPanel";
import {
  AvailBadge,
  btn,
  Card,
  ErrorState,
  FlashMessage,
  inputCls,
  ItemBadge,
  labelCls,
  Loading,
  OverdueBadge,
  ReservationBadge,
  type Flash,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { defaultSlot, dueText, fmtDateTime, fmtRange, toIso } from "@/lib/time";
import type { BusyPeriod, ItemBrief, ItemFull } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

type Detail = { item: ItemFull; current_rental: BusyPeriod | null; busy: BusyPeriod[]; siblings: ItemBrief[] };

function initialPeriod(start: string | null, end: string | null): Period {
  const d = defaultSlot();
  if (start && end) {
    const [sd, st] = start.slice(0, 16).split("T");
    const [ed, et] = end.slice(0, 16).split("T");
    return { startDate: sd, startTime: st, endDate: ed, endTime: et };
  }
  return d;
}

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const user = useUser();
  const isAdmin = user.role === "admin";
  const { data, error, loading, reload } = useLoad<Detail>(/^\d+$/.test(id) ? `/items/${id}` : null);

  if (!/^\d+$/.test(id)) return <ErrorState message="잘못된 물품 주소입니다." />;
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return null;
  const { item, current_rental, busy, siblings } = data;

  return (
    <>
      <BackLink href="/items">물품 목록</BackLink>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="grid content-start gap-6">
          <Card>
            <ItemThumb item={item} size="lg" />
            <div className="mt-4 flex flex-wrap items-start justify-between gap-2">
              <div>
                <h1 className="text-2xl font-bold">{item.name}</h1>
                <p className="font-mono text-sm text-navy-600">관리번호 {item.asset_code}</p>
              </div>
              <ItemBadge status={item.status} />
            </div>
            <dl className="mt-4 grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
              <dt className="font-semibold text-navy-600">카테고리</dt>
              <dd>{item.category}</dd>
              <dt className="font-semibold text-navy-600">보관 장소</dt>
              <dd>{item.location || "-"}</dd>
            </dl>
            {item.description && (
              <div className="mt-4">
                <h2 className="text-sm font-bold text-navy-700">설명</h2>
                <p className="mt-1 whitespace-pre-line text-sm">{item.description}</p>
              </div>
            )}
            {item.caution && (
              <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-3">
                <h2 className="text-sm font-bold text-amber-900">⚠ 사용 주의사항</h2>
                <p className="mt-1 whitespace-pre-line text-sm text-amber-950">{item.caution}</p>
              </div>
            )}
            {isAdmin && (
              <div className="mt-4">
                <Link href={`/admin/items/${item.id}/edit`} className={btn.secondary}>
                  물품 정보 수정
                </Link>
              </div>
            )}
          </Card>
          {siblings.length > 0 && (
            <Card>
              <h2 className="font-bold">같은 종류의 다른 물품</h2>
              <ul className="mt-3 flex flex-wrap gap-2">
                {siblings.map((s) => (
                  <li key={s.id}>
                    <Link href={`/items/${s.id}`} className={`${btn.small} gap-1`}>
                      <span className="font-mono">{s.asset_code}</span>
                      {s.status !== "normal" && <span className="text-orange-800">({s.status === "repair" ? "수리 중" : "보관 종료"})</span>}
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {isAdmin && (
            <Card className="no-print">
              <h2 className="mb-3 font-bold">QR 코드</h2>
              <QrPanel item={item} />
            </Card>
          )}
        </div>

        <div className="grid content-start gap-6">
          <Card>
            <h2 className="text-lg font-bold">현재 상태</h2>
            {item.status === "repair" && (
              <p className="mt-2 rounded-lg bg-orange-50 p-3 text-sm font-semibold text-orange-900">🔧 수리 중이라 지금은 예약할 수 없습니다.</p>
            )}
            {item.status === "retired" && (
              <p className="mt-2 rounded-lg bg-slate-100 p-3 text-sm font-semibold text-slate-800">보관 종료된 물품이라 더 이상 대여하지 않습니다.</p>
            )}
            {current_rental ? (
              <div className={`mt-3 rounded-lg border p-3 ${current_rental.overdue ? "border-rose-300 bg-rose-50" : "border-teal-200 bg-teal-50"}`}>
                <p className="flex flex-wrap items-center gap-2 font-semibold">
                  현재 대여 중 {current_rental.mine && "(내가 빌림)"}
                  {current_rental.overdue && <OverdueBadge />}
                  {isAdmin && current_rental.user_name && <span className="text-sm font-normal">· {current_rental.user_name}</span>}
                </p>
                <p className="mt-1 text-sm">
                  반납 기한 {fmtDateTime(current_rental.end_at)} ({dueText(current_rental.end_at)})
                </p>
              </div>
            ) : (
              item.status === "normal" && <p className="mt-2 text-sm text-navy-700">지금은 대여 중이 아니며 보관 장소에 있습니다.</p>
            )}

            <h3 className="mt-5 text-sm font-bold text-navy-700">사용 불가능한 기간 (확정된 예약·대여)</h3>
            {busy.length === 0 ? (
              <p className="mt-1 text-sm text-navy-600">확정된 예약이 없습니다.</p>
            ) : (
              <ul className="mt-2 grid gap-1.5 text-sm">
                {busy.map((b, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-2 rounded-md bg-navy-50 px-3 py-2">
                    <span className="font-semibold">{fmtRange(b.start_at, b.end_at)}</span>
                    <ReservationBadge status={b.status} overdue={b.overdue} />
                    {b.mine && <span className="text-xs font-semibold text-teal-800">내 예약</span>}
                    {isAdmin && b.user_name && <span className="text-xs text-navy-600">{b.user_name}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {item.status === "normal" && (
            <ReserveForm itemId={item.id} initial={initialPeriod(params.get("start"), params.get("end"))} onDone={reload} />
          )}
          <ReportForm itemId={item.id} />
        </div>
      </div>
    </>
  );
}

function ReserveForm({ itemId, initial, onDone }: { itemId: number; initial: Period; onDone: () => void }) {
  const [period, setPeriod] = useState<Period>(initial);
  const [purpose, setPurpose] = useState("");
  const [check, setCheck] = useState<{ available: boolean; reason: string | null } | null>(null);
  const [checking, setChecking] = useState(false);
  const [flash, setFlash] = useState<Flash>(null);
  const [busy, setBusy] = useState(false);
  const localError = periodError(period);

  // 기간을 바꾸면 선택 기간 예약 가능 여부를 서버에서 다시 확인
  useEffect(() => {
    if (localError) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCheck(null);
      return;
    }
    let cancelled = false;
    setChecking(true);
    const t = setTimeout(async () => {
      try {
        const qs = new URLSearchParams({
          start: toIso(period.startDate, period.startTime),
          end: toIso(period.endDate, period.endTime),
        });
        const res = await api<{ available: boolean; reason: string | null }>(`/items/${itemId}/availability?${qs}`);
        if (!cancelled) setCheck(res);
      } catch (e) {
        if (!cancelled) setCheck({ available: false, reason: errorMessage(e) });
      } finally {
        if (!cancelled) setChecking(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [period, itemId, localError]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFlash(null);
    if (localError) return setFlash({ kind: "error", text: localError });
    if (purpose.trim().length < 2) return setFlash({ kind: "error", text: "사용 목적을 2자 이상 입력해 주세요." });
    setBusy(true);
    try {
      await api("/reservations", {
        body: {
          item_id: itemId,
          start_at: toIso(period.startDate, period.startTime),
          end_at: toIso(period.endDate, period.endTime),
          purpose: purpose.trim(),
        },
      });
      setPurpose("");
      setFlash({ kind: "ok", text: "예약 신청이 접수되었습니다. 관리자가 승인하면 '나의 예약·대여'에서 확인할 수 있습니다." });
      onDone();
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-lg font-bold">예약 신청</h2>
      <p className="mt-1 text-sm text-navy-600">신청 → 관리자 승인 → 보관 장소에서 물품을 받으면 대여가 시작됩니다.</p>
      <form onSubmit={submit} className="mt-4 grid gap-4" noValidate>
        <PeriodFields value={period} onChange={setPeriod} idPrefix="reserve" invalid={!!localError} />
        <div aria-live="polite" className="min-h-6 text-sm">
          {localError ? (
            <span className="font-semibold text-rose-800">{localError}</span>
          ) : checking ? (
            <span className="text-navy-600">예약 가능 여부 확인 중…</span>
          ) : check ? (
            check.available ? (
              <AvailBadge ok>선택한 기간에 예약 신청 가능</AvailBadge>
            ) : (
              <AvailBadge ok={false}>{check.reason ?? "선택한 기간에는 예약할 수 없습니다."}</AvailBadge>
            )
          ) : null}
        </div>
        <label className={labelCls}>
          사용 목적
          <input
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            maxLength={200}
            placeholder="예: 학생회 정기 회의 발표"
            className={inputCls}
            required
          />
        </label>
        <FlashMessage flash={flash} />
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy || !!localError || check?.available === false} className={btn.primary}>
            {busy ? "신청 중…" : "예약 신청"}
          </button>
          {flash?.kind === "ok" && (
            <Link href="/me" className={btn.secondary}>
              나의 예약 보기
            </Link>
          )}
        </div>
      </form>
    </Card>
  );
}

function ReportForm({ itemId }: { itemId: number }) {
  const params = useSearchParams();
  const fromReservation = params.get("reservation");
  const [open, setOpen] = useState(Boolean(fromReservation));
  const [text, setText] = useState("");
  const [flash, setFlash] = useState<Flash>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFlash(null);
    if (text.trim().length < 5) return setFlash({ kind: "error", text: "고장·파손 내용을 5자 이상 입력해 주세요." });
    setBusy(true);
    try {
      await api("/reports", {
        body: { item_id: itemId, description: text.trim(), reservation_id: fromReservation ? Number(fromReservation) : null },
      });
      setText("");
      setFlash({ kind: "ok", text: "고장 신고가 접수되었습니다. 처리 상태는 '나의 예약·대여'에서 확인할 수 있습니다." });
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-bold" id="report">고장·파손 신고</h2>
        <button type="button" className={btn.small} aria-expanded={open} aria-controls="report-form" onClick={() => setOpen(!open)}>
          {open ? "접기" : "신고하기"}
        </button>
      </div>
      {open && (
        <form id="report-form" onSubmit={submit} className="mt-4 grid gap-3" noValidate>
          {fromReservation && <p className="text-sm text-navy-600">예약 #{fromReservation}과 연결해 신고합니다.</p>}
          <label className={labelCls}>
            고장 내용
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              maxLength={2000}
              placeholder="어떤 문제가 있는지 구체적으로 적어 주세요."
              className={inputCls}
              required
            />
          </label>
          <FlashMessage flash={flash} />
          <button type="submit" disabled={busy} className={`${btn.danger} justify-self-start`}>
            {busy ? "접수 중…" : "고장 신고 접수"}
          </button>
        </form>
      )}
    </Card>
  );
}
