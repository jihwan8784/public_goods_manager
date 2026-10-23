import type { ItemStatus, OrgKind, ReportStatus, ReservationStatus } from "./types";

export const ORG_KIND_LABEL: Record<OrgKind, string> = {
  school: "학교",
  community_center: "주민센터",
  other: "기타 기관",
};

export const ORG_KIND_ICON: Record<OrgKind, string> = {
  school: "🏫",
  community_center: "🏛",
  other: "🏢",
};

export const RESERVATION_LABEL: Record<ReservationStatus, string> = {
  pending: "승인 대기",
  approved: "예약 확정",
  rejected: "거절",
  cancelled: "취소",
  in_use: "대여 중",
  return_requested: "반납 요청",
  returned: "반납 완료",
};

export const RESERVATION_TONE: Record<ReservationStatus, string> = {
  pending: "bg-amber-50 text-amber-900 ring-amber-300",
  approved: "bg-sky-50 text-sky-900 ring-sky-300",
  rejected: "bg-rose-50 text-rose-900 ring-rose-300",
  cancelled: "bg-slate-100 text-slate-700 ring-slate-300",
  in_use: "bg-teal-50 text-teal-900 ring-teal-300",
  return_requested: "bg-violet-50 text-violet-900 ring-violet-300",
  returned: "bg-slate-100 text-slate-700 ring-slate-300",
};

export const RESERVATION_ICON: Record<ReservationStatus, string> = {
  pending: "⏳",
  approved: "✔",
  rejected: "✕",
  cancelled: "–",
  in_use: "▶",
  return_requested: "↩",
  returned: "■",
};

export const ITEM_LABEL: Record<ItemStatus, string> = {
  normal: "정상",
  repair: "수리 중",
  retired: "보관 종료",
};

export const ITEM_TONE: Record<ItemStatus, string> = {
  normal: "bg-emerald-50 text-emerald-900 ring-emerald-300",
  repair: "bg-orange-50 text-orange-900 ring-orange-300",
  retired: "bg-slate-100 text-slate-700 ring-slate-300",
};

export const REPORT_LABEL: Record<ReportStatus, string> = {
  received: "접수",
  in_progress: "수리 중",
  resolved: "처리 완료",
  dismissed: "이상 없음",
};

export const REPORT_TONE: Record<ReportStatus, string> = {
  received: "bg-amber-50 text-amber-900 ring-amber-300",
  in_progress: "bg-orange-50 text-orange-900 ring-orange-300",
  resolved: "bg-emerald-50 text-emerald-900 ring-emerald-300",
  dismissed: "bg-slate-100 text-slate-700 ring-slate-300",
};
