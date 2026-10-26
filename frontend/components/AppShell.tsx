"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import { AuthProvider, useAuth } from "./AuthProvider";
import Logo from "./Logo";
import { btn, ErrorState, Forbidden, Loading } from "./ui";

const USER_NAV = [
  { href: "/", label: "홈" },
  { href: "/map", label: "지도" },
  { href: "/items", label: "물품 찾기" },
  { href: "/me", label: "나의 예약·대여" },
  { href: "/me/profile", label: "내 정보" },
];
const STAFF_NAV = [
  { href: "/admin/reservations", label: "예약·대여 관리" },
  { href: "/admin/items", label: "물품 관리" },
  { href: "/admin/reports", label: "고장 신고" },
];
const SUPER_NAV = [
  { href: "/admin/orgs", label: "기관" },
  { href: "/admin/users", label: "회원" },
];
const SUPER_ONLY = ["/admin/orgs", "/admin/users"];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/me") return pathname === "/me";
  return pathname === href || pathname.startsWith(href + "/");
}

function Shell({ children }: { children: ReactNode }) {
  const { user, loading, error, refresh, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const navRef = useRef<HTMLUListElement>(null);

  // 좁은 화면에서 메뉴가 가로로 넘칠 때 현재 메뉴가 보이도록 스크롤
  useEffect(() => {
    navRef.current
      ?.querySelector('[aria-current="page"]')
      ?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [pathname, user]);

  useEffect(() => {
    if (!loading && !user && !error) {
      const next = window.location.pathname + window.location.search;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    }
  }, [loading, user, error, router]);

  if (loading || (!user && !error)) {
    return (
      <div className="mx-auto max-w-6xl px-4">
        <Loading label="로그인 정보를 확인하는 중…" />
      </div>
    );
  }
  if (!user) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10">
        <ErrorState message={error ?? "로그인 정보를 확인하지 못했습니다."} onRetry={refresh} />
      </div>
    );
  }

  const isSuper = user.role === "admin";
  const managesSchool = user.managed_orgs.some((o) => o.kind === "school");
  const nav = [
    ...USER_NAV,
    ...(user.is_staff ? STAFF_NAV : []),
    ...(isSuper || managesSchool ? [{ href: "/admin/students", label: "학생 승인" }] : []),
    ...(isSuper ? SUPER_NAV : []),
  ];
  const adminArea = pathname.startsWith("/admin");
  const forbidden =
    (adminArea && !user.is_staff) || (SUPER_ONLY.some((p) => pathname.startsWith(p)) && !isSuper);

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        본문 바로가기
      </a>
      <header className="no-print border-b border-navy-800 bg-navy-900 text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link href="/" className="flex items-center gap-2 font-bold tracking-tight">
            <Logo size={32} className="rounded-lg ring-1 ring-white/25" />
            public goods manage
          </Link>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-navy-100">
              {user.name}
              {(isSuper || user.is_staff) && (
                <span className="ml-1.5 rounded bg-teal-500 px-1.5 py-0.5 text-xs font-bold text-navy-900">
                  {isSuper ? "최고 관리자" : "기관 관리자"}
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={logout}
              className="rounded-md border border-navy-500 px-2.5 py-1 font-semibold hover:bg-navy-800"
            >
              로그아웃
            </button>
          </div>
        </div>
        <nav aria-label="주요 메뉴" className="border-t border-navy-800">
          {/* 오른쪽 끝을 흐리게 해서 메뉴가 더 있다는 것을 보여 줌 (넓은 화면에서는 없음) */}
          <ul
            ref={navRef}
            className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-2 text-sm [mask-image:linear-gradient(to_right,black_85%,transparent)] [scrollbar-width:none] lg:[mask-image:none]"
          >
            {nav.map((n) => {
              const active = isActive(pathname, n.href);
              return (
                <li key={n.href} className="shrink-0">
                  <Link
                    href={n.href}
                    aria-current={active ? "page" : undefined}
                    className={`block border-b-[3px] px-3 py-2.5 font-semibold ${
                      active ? "border-teal-400 text-white" : "border-transparent text-navy-200 hover:text-white"
                    }`}
                  >
                    {n.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8">
        {forbidden ? <Forbidden /> : children}
      </main>
      <footer className="no-print border-t border-navy-100 py-4 text-center text-xs text-navy-500">
        public goods manage · 모든 시간은 한국 시간(KST) 기준
      </footer>
    </div>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <Shell>{children}</Shell>
    </AuthProvider>
  );
}

export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className={`${btn.small} no-print mb-4`}>
      ← {children}
    </Link>
  );
}
