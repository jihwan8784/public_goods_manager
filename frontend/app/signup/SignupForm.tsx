"use client";

import { useState } from "react";
import OrgPicker from "@/components/OrgPicker";
import { btn, inputCls, labelCls } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { OrgBrief } from "@/lib/types";

type School = OrgBrief & { address: string };
type Errors = Partial<Record<"email" | "name" | "password" | "password2" | "school" | "student_no", string>>;

export default function SignupForm() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [isStudent, setIsStudent] = useState<boolean | null>(null);
  const [school, setSchool] = useState<School | null>(null);
  const [studentNo, setStudentNo] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  function validate(): boolean {
    const e: Errors = {};
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) e.email = "이메일 형식으로 입력해 주세요.";
    if (!name.trim()) e.name = "이름을 입력해 주세요.";
    if (password.length < 8) e.password = "비밀번호는 8자 이상이어야 합니다.";
    if (password !== password2) e.password2 = "비밀번호가 서로 다릅니다.";
    if (isStudent) {
      if (!school) e.school = "다니는 학교를 검색해서 선택해 주세요.";
      if (!studentNo.trim()) e.student_no = "학번(또는 학년·반·번호)을 입력해 주세요.";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    setFormError("");
    if (isStudent === null) {
      setFormError("학생인지 선택해 주세요.");
      return;
    }
    if (!validate()) {
      setFormError("입력값을 확인해 주세요.");
      return;
    }
    setBusy(true);
    try {
      await api("/auth/signup", {
        body: {
          email: email.trim(),
          name: name.trim(),
          password,
          is_student: isStudent,
          school_id: isStudent ? school?.id : null,
          student_no: isStudent ? studentNo.trim() : null,
        },
        noRedirect: true,
      });
      window.location.assign(isStudent ? "/me/profile?welcome=student" : "/?welcome=1");
    } catch (err) {
      setFormError(errorMessage(err));
      setBusy(false);
    }
  }

  const err = (k: keyof Errors) =>
    errors[k] ? (
      <span id={`${k}-err`} className="text-xs font-semibold text-rose-800">
        {errors[k]}
      </span>
    ) : null;

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-xl border border-navy-100 bg-white p-6 shadow-sm" noValidate>
      <label className={labelCls}>
        이메일 (로그인 아이디)
        <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} aria-invalid={!!errors.email} aria-describedby="email-err" />
        {err("email")}
      </label>
      <label className={labelCls}>
        이름
        <input autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={50} className={inputCls} aria-invalid={!!errors.name} aria-describedby="name-err" />
        {err("name")}
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={labelCls}>
          비밀번호 (8자 이상)
          <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} aria-invalid={!!errors.password} aria-describedby="password-err" />
          {err("password")}
        </label>
        <label className={labelCls}>
          비밀번호 확인
          <input type="password" autoComplete="new-password" value={password2} onChange={(e) => setPassword2(e.target.value)} className={inputCls} aria-invalid={!!errors.password2} aria-describedby="password2-err" />
          {err("password2")}
        </label>
      </div>

      <fieldset className="grid gap-2 rounded-lg bg-navy-50 p-4">
        <legend className="px-1 text-sm font-semibold text-navy-700">학생인가요?</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="student" checked={isStudent === true} onChange={() => setIsStudent(true)} className="size-4 accent-teal-700" />
          네, 학생이에요 — 우리 학교 물품도 빌리고 싶어요
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="student" checked={isStudent === false} onChange={() => setIsStudent(false)} className="size-4 accent-teal-700" />
          아니요 — 주민센터 등 누구나 빌릴 수 있는 물품만 이용할게요
        </label>
        {isStudent && (
          <div className="mt-2 grid gap-3">
            <OrgPicker label="다니는 학교" kind="school" value={school} onChange={setSchool} invalid={!!errors.school} />
            {err("school")}
            <label className={labelCls}>
              학번 (또는 학년·반·번호)
              <input value={studentNo} onChange={(e) => setStudentNo(e.target.value)} maxLength={40} placeholder="예: 20315 또는 2학년 3반 15번" className={inputCls} aria-invalid={!!errors.student_no} aria-describedby="student_no-err" />
              {err("student_no")}
            </label>
            <p className="rounded-md bg-white p-3 text-xs text-navy-700">
              가입 후 학교 관리자가 학생 여부를 확인해 승인하면 그 학교의 &lsquo;소속 학생 전용&rsquo; 물품을 빌릴 수 있습니다. 승인 전에도 누구나 빌릴 수 있는 물품은 이용할 수 있어요.
            </p>
          </div>
        )}
      </fieldset>

      {formError && (
        <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800">
          {formError}
        </p>
      )}
      <button type="submit" disabled={busy} className={btn.primary}>
        {busy ? "가입하는 중…" : "가입하기"}
      </button>
    </form>
  );
}
