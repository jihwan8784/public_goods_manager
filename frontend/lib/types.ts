export type Role = "user" | "admin";
export type User = { id: number; email: string; name: string; role: Role };

export type ItemStatus = "normal" | "repair" | "retired";
export type ItemBrief = {
  id: number;
  asset_code: string;
  name: string;
  category: string;
  location: string;
  status: ItemStatus;
  has_image: boolean;
  image_version: number;
};
export type ItemFull = ItemBrief & { description: string; caution: string; updated_at: string };

export type ItemListRow = ItemBrief & {
  rented: boolean;
  rented_due: string | null;
  rented_overdue: boolean;
  period?: { available: boolean; reason: string | null };
};

export type ReservationStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled"
  | "in_use"
  | "return_requested"
  | "returned";

export type Reservation = {
  id: number;
  item: ItemBrief | null;
  user: { id: number; name: string; email: string } | null;
  start_at: string;
  end_at: string;
  purpose: string;
  status: ReservationStatus;
  status_label: string;
  overdue: boolean;
  reject_reason: string | null;
  cancel_reason: string | null;
  decided_at: string | null;
  cancelled_at: string | null;
  checked_out_at: string | null;
  return_requested_at: string | null;
  return_request_note: string | null;
  returned_at: string | null;
  return_condition: "normal" | "needs_repair" | null;
  return_note: string | null;
  created_at: string;
  // 관리자 목록 전용
  conflicts?: number[];
  pending_overlaps?: number[];
  item_blocked?: boolean;
  blockers?: string[];
};

export type BusyPeriod = {
  start_at: string;
  end_at: string;
  status: ReservationStatus;
  status_label: string;
  overdue: boolean;
  mine: boolean;
  reservation_id?: number;
  user_name?: string | null;
};

export type ReportStatus = "received" | "in_progress" | "resolved" | "dismissed";
export type Report = {
  id: number;
  item: ItemBrief | null;
  reporter: { id: number; name: string } | null;
  reservation_id: number | null;
  description: string;
  status: ReportStatus;
  admin_note: string;
  created_at: string;
  updated_at: string;
};
