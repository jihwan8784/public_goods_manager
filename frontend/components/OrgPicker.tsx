"use client";

import { useEffect, useId, useState } from "react";
import { api } from "@/lib/api";
import { ORG_KIND_ICON } from "@/lib/labels";
import type { OrgBrief, OrgKind } from "@/lib/types";
import { inputCls, labelCls } from "./ui";

type Found = OrgBrief & { address: string };

/** 기관(학교 등) 이름으로 검색해서 하나 고르기 */
export default function OrgPicker({
  label,
  kind,
  value,
  onChange,
  invalid,
  placeholder = "학교 이름을 2글자 이상 입력하세요",
}: {
  label: string;
  kind?: OrgKind;
  value: Found | null;
  onChange: (org: Found | null) => void;
  invalid?: boolean;
  placeholder?: string;
}) {
  const id = useId();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Found[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResults([]);
      return;
    }
    let alive = true;
    setState("loading");
    const t = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: term, limit: "15" });
        if (kind) params.set("kind", kind);
        const res = await api<{ orgs: Found[] }>(`/orgs/search?${params}`, { noRedirect: true });
        if (alive) {
          setResults(res.orgs);
          setState("idle");
        }
      } catch {
        if (alive) setState("error");
      }
    }, 250);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q, kind]);

  if (value) {
    return (
      <div className={labelCls}>
        <span>{label}</span>
        <div className="flex items-center justify-between gap-2 rounded-lg border border-teal-600 bg-teal-50 px-3 py-2 font-normal">
          <span>
            <span className="font-semibold text-navy-900">{value.name}</span>
            <span className="block text-xs text-navy-600">{value.address || value.region}</span>
          </span>
          <button type="button" className="text-sm font-semibold text-teal-800 underline" onClick={() => onChange(null)}>
            다시 선택
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-1">
      <label htmlFor={id} className={labelCls}>
        {label}
      </label>
      <input
        id={id}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder}
        className={inputCls}
        aria-invalid={invalid}
        aria-describedby={`${id}-status`}
        autoComplete="off"
      />
      <p id={`${id}-status`} className="text-xs text-navy-600" aria-live="polite">
        {state === "loading"
          ? "찾는 중…"
          : state === "error"
            ? "검색하지 못했습니다. 잠시 후 다시 시도해 주세요."
            : q.trim().length >= 2 && results.length === 0
              ? "검색 결과가 없습니다. 정식 이름(예: ○○고등학교)으로 찾아보세요."
              : results.length > 0
                ? `${results.length}곳 찾음 — 아래에서 선택하세요`
                : ""}
      </p>
      {results.length > 0 && (
        <ul className="max-h-60 overflow-y-auto rounded-lg border border-navy-100 bg-white">
          {results.map((o) => (
            <li key={o.id}>
              <button
                type="button"
                onClick={() => onChange(o)}
                className="block w-full border-b border-navy-50 px-3 py-2 text-left text-sm hover:bg-navy-50 focus:bg-navy-50"
              >
                <span aria-hidden>{ORG_KIND_ICON[o.kind]} </span>
                <span className="font-semibold">{o.name}</span>
                <span className="block text-xs text-navy-600">{o.address || o.region}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
