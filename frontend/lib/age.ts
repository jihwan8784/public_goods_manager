import { seoulParts } from "./time";

/** 가입 가능한 최소 만 나이 (서버 config.MIN_SIGNUP_AGE 와 같게 유지) */
export const MIN_SIGNUP_AGE = 14;

export function todaySeoul(): string {
  return seoulParts(new Date()).date;
}

/** 만 나이. birth·today 는 YYYY-MM-DD */
export function ageOn(birth: string, today = todaySeoul()): number {
  const [by, bm, bd] = birth.split("-").map(Number);
  const [ty, tm, td] = today.split("-").map(Number);
  return ty - by - (tm < bm || (tm === bm && td < bd) ? 1 : 0);
}

/** 화면에서 먼저 보여 주는 안내 (최종 확인은 서버가 함) */
export function birthDateError(birth: string): string | null {
  if (!birth) return "생년월일을 입력해 주세요.";
  if (birth >= todaySeoul()) return "생년월일을 다시 확인해 주세요.";
  const age = ageOn(birth);
  if (age > 100) return "생년월일을 다시 확인해 주세요.";
  if (age < MIN_SIGNUP_AGE) return `만 ${MIN_SIGNUP_AGE}세 미만은 보호자 동의가 필요해 아직 가입할 수 없습니다.`;
  return null;
}
