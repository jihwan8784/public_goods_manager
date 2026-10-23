"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import ItemThumb from "@/components/ItemThumb";
import { btn, Card, FlashMessage, inputCls, labelCls, type Flash } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { fmtRange } from "@/lib/time";
import type { ItemFull, ItemStatus, Reservation } from "@/lib/types";

type Values = {
  asset_code: string;
  name: string;
  category: string;
  description: string;
  caution: string;
  location: string;
  status: ItemStatus;
};

const EMPTY: Values = { asset_code: "", name: "", category: "", description: "", caution: "", location: "", status: "normal" };

/** 큰 사진은 업로드 전에 브라우저에서 줄인다 (최대 1200px JPEG) */
async function shrink(file: File): Promise<Blob> {
  if (file.type === "image/gif" || file.size < 300_000) return file;
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, 1200 / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * scale);
  canvas.height = Math.round(bmp.height * scale);
  canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("이미지 변환 실패"))), "image/jpeg", 0.85),
  );
}

export default function ItemForm({
  item,
  categories,
  canDelete,
  onSaved,
}: {
  item?: ItemFull;
  categories: string[];
  canDelete?: boolean;
  onSaved?: () => void;
}) {
  const router = useRouter();
  const [v, setV] = useState<Values>(item ? { ...item } : EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof Values, string>>>({});
  const [flash, setFlash] = useState<Flash>(null);
  const [saving, setSaving] = useState(false);
  const [affected, setAffected] = useState<Reservation[]>([]);
  const [uploading, setUploading] = useState(false);

  const set = (k: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setV({ ...v, [k]: e.target.value });

  function validate(): boolean {
    const e: typeof errors = {};
    if (!/^[A-Za-z0-9][A-Za-z0-9\-_]{1,39}$/.test(v.asset_code.trim())) e.asset_code = "영문·숫자·-·_ 로 2~40자 (예: MIC-001)";
    if (!v.name.trim()) e.name = "물품명을 입력해 주세요.";
    if (!v.category.trim()) e.category = "카테고리를 입력해 주세요.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setFlash(null);
    if (!validate()) {
      setFlash({ kind: "error", text: "입력값을 확인해 주세요." });
      return;
    }
    setSaving(true);
    try {
      if (item) {
        const res = await api<{ item: ItemFull; affected: Reservation[] }>(`/admin/items/${item.id}`, { method: "PUT", body: v });
        setAffected(res.affected);
        setV({ ...res.item });
        setFlash({ kind: "ok", text: "저장했습니다." });
        onSaved?.();
      } else {
        const res = await api<{ item: ItemFull }>("/admin/items", { body: v });
        router.push(`/admin/items/${res.item.id}/edit?created=1`);
      }
    } catch (err) {
      setFlash({ kind: "error", text: `저장하지 못했습니다: ${errorMessage(err)}` });
    } finally {
      setSaving(false);
    }
  }

  async function upload(file: File | undefined) {
    if (!file || !item) return;
    setFlash(null);
    if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type)) {
      setFlash({ kind: "error", text: "JPG, PNG, WEBP, GIF 이미지만 올릴 수 있습니다." });
      return;
    }
    setUploading(true);
    try {
      const blob = await shrink(file);
      const form = new FormData();
      form.append("file", blob, file.name);
      await api(`/admin/items/${item.id}/image`, { form, method: "POST" });
      setFlash({ kind: "ok", text: "사진을 저장했습니다." });
      onSaved?.();
    } catch (err) {
      setFlash({ kind: "error", text: `사진을 올리지 못했습니다: ${errorMessage(err)}` });
    } finally {
      setUploading(false);
    }
  }

  async function removeImage() {
    if (!item) return;
    try {
      await api(`/admin/items/${item.id}/image`, { method: "DELETE" });
      setFlash({ kind: "ok", text: "사진을 삭제했습니다. 기본 이미지가 표시됩니다." });
      onSaved?.();
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    }
  }

  async function remove() {
    if (!item || !window.confirm(`${item.asset_code}을(를) 완전히 삭제할까요? 되돌릴 수 없습니다.`)) return;
    try {
      await api(`/admin/items/${item.id}`, { method: "DELETE" });
      router.push("/admin/items");
    } catch (err) {
      setFlash({ kind: "error", text: errorMessage(err) });
    }
  }

  const field = (k: keyof Values, label: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className={labelCls}>
      {label}
      <input value={v[k]} onChange={set(k)} className={inputCls} aria-invalid={!!errors[k]} aria-describedby={errors[k] ? `${k}-err` : undefined} {...extra} />
      {errors[k] && <span id={`${k}-err`} className="text-xs font-semibold text-rose-800">{errors[k]}</span>}
    </label>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <Card>
        <form onSubmit={save} className="grid gap-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            {field("name", "물품명 (종류)", { placeholder: "예: 무선 마이크", maxLength: 80, required: true })}
            {field("asset_code", "개별 관리번호", { placeholder: "예: MIC-004", maxLength: 40, required: true, className: `${inputCls} font-mono uppercase` })}
            <label className={labelCls}>
              카테고리
              <input value={v.category} onChange={set("category")} list="category-list" className={inputCls} aria-invalid={!!errors.category} maxLength={40} required />
              <datalist id="category-list">
                {categories.map((c) => <option key={c} value={c} />)}
              </datalist>
              {errors.category && <span className="text-xs font-semibold text-rose-800">{errors.category}</span>}
            </label>
            {field("location", "보관 장소", { placeholder: "예: 학생회실 A캐비닛", maxLength: 120 })}
          </div>
          <label className={labelCls}>
            설명
            <textarea value={v.description} onChange={set("description")} rows={3} maxLength={4000} className={inputCls} />
          </label>
          <label className={labelCls}>
            사용 주의사항
            <textarea value={v.caution} onChange={set("caution")} rows={3} maxLength={4000} className={inputCls} />
          </label>
          {item && (
            <label className={labelCls}>
              물품 상태
              <select value={v.status} onChange={set("status")} className={inputCls}>
                <option value="normal">정상</option>
                <option value="repair">수리 중 (신규 승인·대여 시작 차단)</option>
                <option value="retired">보관 종료 (더 이상 대여하지 않음, 기록 보존)</option>
              </select>
            </label>
          )}
          <FlashMessage flash={flash} />
          {affected.length > 0 && (
            <div role="alert" className="rounded-lg border border-orange-300 bg-orange-50 p-4 text-sm">
              <p className="font-bold text-orange-900">영향을 받는 예약 {affected.length}건</p>
              <ul className="mt-2 grid gap-1">
                {affected.map((a) => (
                  <li key={a.id}>#{a.id} · {a.user?.name} · {fmtRange(a.start_at, a.end_at)} · {a.status_label}</li>
                ))}
              </ul>
              <Link href="/admin/reservations?tab=all" className="mt-2 inline-block font-semibold text-orange-900 underline">예약 관리에서 처리하기</Link>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={saving} className={btn.primary}>{saving ? "저장 중…" : item ? "변경 저장" : "등록"}</button>
            <Link href="/admin/items" className={btn.secondary}>목록으로</Link>
            {item && canDelete && (
              <button type="button" className={btn.danger} onClick={remove}>삭제 (기록 없음)</button>
            )}
          </div>
          {item && !canDelete && (
            <p className="text-xs text-navy-600">대여·신고 기록이 있어 삭제할 수 없습니다. 더 이상 쓰지 않는다면 상태를 &apos;보관 종료&apos;로 바꿔 주세요.</p>
          )}
        </form>
      </Card>
      {item && (
        <Card className="content-start">
          <h2 className="font-bold">사진</h2>
          <div className="mt-3 max-w-xs"><ItemThumb item={item} size="lg" /></div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label className={`${btn.secondary} cursor-pointer focus-within:outline focus-within:outline-3 focus-within:outline-teal-600`}>
              {uploading ? "올리는 중…" : item.has_image ? "사진 바꾸기" : "사진 올리기"}
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" className="sr-only" disabled={uploading} onChange={(e) => upload(e.target.files?.[0])} />
            </label>
            {item.has_image && <button type="button" className={btn.danger} onClick={removeImage}>사진 삭제</button>}
          </div>
          <p className="mt-2 text-xs text-navy-600">사진이 없으면 카테고리별 기본 이미지가 표시됩니다. (2MB 이하, 큰 사진은 자동으로 줄여서 저장)</p>
        </Card>
      )}
    </div>
  );
}
