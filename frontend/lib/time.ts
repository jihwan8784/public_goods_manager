// 모든 시간은 Asia/Seoul 기준으로 보여 주고, 서버에는 +09:00 오프셋을 붙여 보낸다.
// (한국은 일광 절약 시간이 없어 +09:00 고정)
export const TZ = "Asia/Seoul";

const dateTimeFmt = new Intl.DateTimeFormat("ko-KR", {
  timeZone: TZ,
  month: "long",
  day: "numeric",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const timeFmt = new Intl.DateTimeFormat("ko-KR", {
  timeZone: TZ,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const partsFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function fmtDateTime(iso: string | Date): string {
  return dateTimeFmt.format(new Date(iso));
}

export function seoulParts(d: Date): { date: string; time: string } {
  const p = Object.fromEntries(partsFmt.formatToParts(d).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}` };
}

export function fmtRange(a: string, b: string): string {
  const sa = seoulParts(new Date(a));
  const sb = seoulParts(new Date(b));
  if (sa.date === sb.date) return `${fmtDateTime(a)} ~ ${timeFmt.format(new Date(b))}`;
  return `${fmtDateTime(a)} ~ ${fmtDateTime(b)}`;
}

/** 입력값(서울 날짜·시각)을 서버로 보낼 ISO 문자열로 */
export function toIso(date: string, time: string): string {
  return `${date}T${time}:00+09:00`;
}

/** 다음 정각(30분 단위) 기본값 */
export function defaultSlot(hoursFromNow = 1, lengthHours = 2) {
  const start = new Date(Date.now() + hoursFromNow * 3600_000);
  start.setUTCMinutes(start.getUTCMinutes() < 30 ? 30 : 60, 0, 0);
  const end = new Date(start.getTime() + lengthHours * 3600_000);
  const s = seoulParts(start);
  const e = seoulParts(end);
  return { startDate: s.date, startTime: s.time, endDate: e.date, endTime: e.time };
}

export const TIME_SLOTS: string[] = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, "0");
  return `${h}:${i % 2 ? "30" : "00"}`;
});

/** 반납 기한까지 남은 시간 / 지난 시간 */
export function dueText(endIso: string, now = Date.now()): string {
  const diff = new Date(endIso).getTime() - now;
  const abs = Math.abs(diff);
  const mins = Math.round(abs / 60000);
  let span: string;
  if (mins < 60) span = `${mins}분`;
  else if (mins < 60 * 24) span = `${Math.floor(mins / 60)}시간`;
  else span = `${Math.floor(mins / 1440)}일`;
  return diff >= 0 ? `${span} 남음` : `${span} 지남`;
}
