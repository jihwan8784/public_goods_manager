"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  ITEM_LABEL,
  ITEM_TONE,
  REPORT_LABEL,
  REPORT_TONE,
  RESERVATION_ICON,
  RESERVATION_LABEL,
  RESERVATION_TONE,
} from "@/lib/labels";
import type { ItemStatus, ReportStatus, ReservationStatus } from "@/lib/types";

export const btn = {
  primary:
    "inline-flex items-center justify-center gap-1 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600",
  secondary:
    "inline-flex items-center justify-center gap-1 rounded-lg border border-navy-200 bg-white px-4 py-2 text-sm font-semibold text-navy-800 hover:bg-navy-50 disabled:cursor-not-allowed disabled:opacity-50",
  danger:
    "inline-flex items-center justify-center gap-1 rounded-lg border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50",
  small:
    "inline-flex items-center justify-center rounded-md border border-navy-200 bg-white px-2.5 py-1 text-xs font-semibold text-navy-800 hover:bg-navy-50",
};

// 너비를 따로 지정할 때 쓰는 기본 입력 스타일
export const inputBase =
  "rounded-lg border border-navy-200 bg-white px-3 py-2 text-navy-900 placeholder:text-navy-300 focus:border-teal-600 disabled:bg-slate-100";
export const inputCls =
  "w-full rounded-lg border border-navy-200 bg-white px-3 py-2 text-navy-900 placeholder:text-navy-300 focus:border-teal-600 disabled:bg-slate-100";
export const labelCls = "grid gap-1 text-sm font-semibold text-navy-700";

function Pill({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset ${tone}`}
    >
      {children}
    </span>
  );
}

export function ReservationBadge({ status, overdue }: { status: ReservationStatus; overdue?: boolean }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      <Pill tone={RESERVATION_TONE[status]}>
        <span aria-hidden>{RESERVATION_ICON[status]}</span>
        {RESERVATION_LABEL[status]}
      </Pill>
      {overdue && <OverdueBadge />}
    </span>
  );
}

export function OverdueBadge() {
  return (
    <Pill tone="bg-rose-600 text-white ring-rose-700">
      <span aria-hidden>!</span>연체
    </Pill>
  );
}

export function ItemBadge({ status }: { status: ItemStatus }) {
  return (
    <Pill tone={ITEM_TONE[status]}>
      <span aria-hidden>{status === "normal" ? "●" : status === "repair" ? "🔧" : "▣"}</span>
      {ITEM_LABEL[status]}
    </Pill>
  );
}

export function ReportBadge({ status }: { status: ReportStatus }) {
  return <Pill tone={REPORT_TONE[status]}>{REPORT_LABEL[status]}</Pill>;
}

export function AvailBadge({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <Pill tone={ok ? "bg-teal-600 text-white ring-teal-700" : "bg-white text-rose-800 ring-rose-300"}>
      <span aria-hidden>{ok ? "✔" : "✕"}</span>
      {children}
    </Pill>
  );
}

export function Loading({ label = "불러오는 중…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 py-10 text-navy-600">
      <span className="size-5 animate-spin rounded-full border-2 border-navy-200 border-t-teal-700" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-rose-900">
      <p className="font-semibold">불러오지 못했습니다</p>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className={`${btn.secondary} mt-3`}>
          다시 시도
        </button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-navy-200 bg-white px-5 py-8 text-center">
      <p className="font-semibold text-navy-800">{title}</p>
      {children && <div className="mt-2 text-sm text-navy-600">{children}</div>}
    </div>
  );
}

export function Forbidden() {
  return (
    <div role="alert" className="mx-auto max-w-lg rounded-xl border border-amber-300 bg-amber-50 p-6 text-amber-950">
      <h1 className="text-lg font-bold">접근 권한이 없습니다</h1>
      <p className="mt-2 text-sm">이 화면을 사용할 권한이 없습니다. 기관 관리자 지정이 필요하면 서비스 관리자에게 문의해 주세요.</p>
      <Link href="/" className={`${btn.secondary} mt-4`}>
        홈으로
      </Link>
    </div>
  );
}

export type Flash = { kind: "ok" | "error"; text: string } | null;

export function FlashMessage({ flash, onClose }: { flash: Flash; onClose?: () => void }) {
  return (
    <div aria-live="polite" className="empty:hidden">
      {flash && (
        <div
          role={flash.kind === "error" ? "alert" : "status"}
          className={`flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm font-semibold ${
            flash.kind === "ok"
              ? "border-teal-300 bg-teal-50 text-teal-900"
              : "border-rose-300 bg-rose-50 text-rose-900"
          }`}
        >
          <span>
            {flash.kind === "ok" ? "✔ " : "⚠ "}
            {flash.text}
          </span>
          {onClose && (
            <button type="button" onClick={onClose} className="shrink-0 underline" aria-label="알림 닫기">
              닫기
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function PageHeader({ title, desc, actions }: { title: string; desc?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold text-navy-900">{title}</h1>
        {desc && <p className="mt-1 text-sm text-navy-600">{desc}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-navy-100 bg-white p-5 shadow-sm ${className}`}>{children}</section>;
}

export function LiveBadge({ updatedAt }: { updatedAt: Date | null }) {
  if (!updatedAt) return null;
  const t = updatedAt.toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-navy-600" aria-live="off">
      <span className="size-2 rounded-full bg-teal-500" aria-hidden />
      자동 갱신 중 · {t} 기준
    </span>
  );
}

export function AccessBadge({ access }: { access: "public" | "members" }) {
  return access === "members" ? (
    <Pill tone="bg-indigo-50 text-indigo-900 ring-indigo-300">
      <span aria-hidden>🎓</span>소속 학생 전용
    </Pill>
  ) : (
    <Pill tone="bg-white text-navy-700 ring-navy-200">
      <span aria-hidden>👥</span>누구나
    </Pill>
  );
}
