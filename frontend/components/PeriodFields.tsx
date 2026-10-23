"use client";

import { inputCls, labelCls } from "./ui";
import { TIME_SLOTS } from "@/lib/time";

export type Period = { startDate: string; startTime: string; endDate: string; endTime: string };

export default function PeriodFields({
  value,
  onChange,
  idPrefix,
  invalid,
}: {
  value: Period;
  onChange: (p: Period) => void;
  idPrefix: string;
  invalid?: boolean;
}) {
  const set = (k: keyof Period) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...value, [k]: e.target.value });
  return (
    <fieldset className="grid gap-3 sm:grid-cols-2">
      <legend className="sr-only">사용 기간 (한국 시간)</legend>
      <div className="grid grid-cols-[1fr_7rem] gap-2">
        <label className={labelCls} htmlFor={`${idPrefix}-sd`}>
          시작 날짜
          <input id={`${idPrefix}-sd`} type="date" value={value.startDate} onChange={set("startDate")} className={inputCls} aria-invalid={invalid} required />
        </label>
        <label className={labelCls} htmlFor={`${idPrefix}-st`}>
          시작 시각
          <select id={`${idPrefix}-st`} value={value.startTime} onChange={set("startTime")} className={inputCls} aria-invalid={invalid}>
            {TIME_SLOTS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="grid grid-cols-[1fr_7rem] gap-2">
        <label className={labelCls} htmlFor={`${idPrefix}-ed`}>
          종료 날짜
          <input id={`${idPrefix}-ed`} type="date" value={value.endDate} onChange={set("endDate")} className={inputCls} aria-invalid={invalid} required />
        </label>
        <label className={labelCls} htmlFor={`${idPrefix}-et`}>
          종료 시각
          <select id={`${idPrefix}-et`} value={value.endTime} onChange={set("endTime")} className={inputCls} aria-invalid={invalid}>
            {TIME_SLOTS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
      </div>
    </fieldset>
  );
}

export function periodError(p: Period): string | null {
  if (!p.startDate || !p.endDate) return "날짜를 선택해 주세요.";
  const s = new Date(`${p.startDate}T${p.startTime}:00+09:00`).getTime();
  const e = new Date(`${p.endDate}T${p.endTime}:00+09:00`).getTime();
  if (Number.isNaN(s) || Number.isNaN(e)) return "날짜 형식이 올바르지 않습니다.";
  if (s >= e) return "시작 시각은 종료 시각보다 빨라야 합니다.";
  if (s < Date.now() - 60_000) return "지난 시간으로는 예약할 수 없습니다.";
  return null;
}
