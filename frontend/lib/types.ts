export type Role = "user" | "admin";
export type OrgKind = "school" | "community_center" | "other";
export type OrgBrief = {
  id: number;
  name: string;
  kind: OrgKind;
  subtype: string;
  region: string;
  lat?: number | null;
  lng?: number | null;
};
export type OrgFull = OrgBrief & {
  address: string;
  phone: string;
  geocode_status: "pending" | "ok" | "failed" | "manual";
  source: string;
  active: boolean;
  synced_at: string | null;
};
export type StudentStatus = "none" | "pending" | "approved" | "rejected";
export type User = {
  id: number;
  email: string;
  name: string;
  /** admin = 서비스 전체 관리자 */
  role: Role;
  /** 서비스 관리자이거나 기관 관리자 */
  is_staff: boolean;
  managed_orgs: OrgBrief[];
  student: {
    is_student: boolean;
    school: OrgBrief | null;
    student_no: string | null;
    status: StudentStatus;
    status_label: string;
    reject_reason: string | null;
    birth_date: string | null;
  };
};
export type MapOrg = OrgBrief & {
  address: string;
  lat: number;
  lng: number;
  items: number;
  available_now: number;
  members_only: number;
  my_school: boolean;
};

export type ItemStatus = "normal" | "repair" | "retired";
export type ItemAccess = "public" | "members";
export type ItemBrief = {
  id: number;
  org_id: number | null;
  org: OrgBrief | null;
  access: ItemAccess;
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
  eligible: boolean;
  eligible_reason: string | null;
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
  ineligible_reason?: string | null;
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
