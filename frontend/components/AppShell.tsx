"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AuthProvider, useAuth } from "./AuthProvider";
import Logo from "./Logo";
import { btn, ErrorState, Forbidden, Loading } from "./ui";
import { APP_NAME, APP_TAGLINE } from "@/lib/brand";

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
  const [menuOpen, setMenuOpen] = useState(false);
  // 다른 화면으로 가면 모바일 메뉴를 닫는다
  const [menuPath, setMenuPath] = useState(pathname);
  if (menuPath !== pathname) {
    setMenuPath(pathname);
    setMenuOpen(false);
  }

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

  const roleLabel = isSuper ? "최고 관리자" : user.is_staff ? "기관 관리자" : null;
  const userNav = nav.filter((n) => USER_NAV.includes(n));
  const adminNav = nav.filter((n) => !USER_NAV.includes(n));

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        본문 바로가기
      </a>

      {/* 맨 위 작은 줄: 일반 웹사이트처럼 로그인 정보·내 정보·로그아웃 */}
      <div className="no-print hidden border-b border-navy-100 bg-navy-50 text-xs text-navy-600 md:block">
        <div className="mx-auto flex max-w-6xl items-center justify-end gap-3 px-4 py-1.5">
          <span>
            <b className="font-semibold text-navy-800">{user.name}</b> 님
            {roleLabel && (
              <span className="ml-1.5 rounded bg-teal-50 px-1.5 py-0.5 font-bold text-teal-800 ring-1 ring-inset ring-teal-200">
                {roleLabel}
              </span>
            )}
          </span>
          <span aria-hidden className="text-navy-200">|</span>
          <Link href="/me/profile" className="hover:text-navy-900 hover:underline">
            내 정보
          </Link>
          <span aria-hidden className="text-navy-200">|</span>
          <button type="button" onClick={logout} className="hover:text-navy-900 hover:underline">
            로그아웃
          </button>
        </div>
      </div>

      <header className="no-print sticky top-0 z-40 border-b border-navy-100 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link href="/" className="flex shrink-0 items-center gap-2 text-lg font-extrabold tracking-tight text-navy-900">
            <Logo size={34} className="rounded-lg" />
            <span>
              {APP_NAME.slice(0, 2)}
              <span className="text-teal-700">{APP_NAME.slice(2)}</span>
            </span>
          </Link>
          <HeaderSearch className="ml-auto hidden w-full max-w-sm md:flex" />
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            className="ml-auto rounded-lg border border-navy-200 px-3 py-2 text-sm font-semibold text-navy-800 hover:bg-navy-50 md:hidden"
          >
            <span aria-hidden>{menuOpen ? "✕" : "☰"}</span>
            <span className="sr-only">{menuOpen ? "메뉴 닫기" : "메뉴 열기"}</span>
          </button>
        </div>

        {/* 넓은 화면: 가로 메뉴 */}
        <nav aria-label="주요 메뉴" className="hidden border-t border-navy-100 md:block">
          <ul className="mx-auto flex max-w-6xl items-center gap-1 px-2 text-[15px]">
            {userNav.map((n) => (
              <NavLink key={n.href} item={n} pathname={pathname} />
            ))}
            {adminNav.length > 0 && (
              <>
                <li aria-hidden className="mx-2 h-4 w-px bg-navy-200" />
                <li className="px-1 text-xs font-bold text-navy-400">관리</li>
                {adminNav.map((n) => (
                  <NavLink key={n.href} item={n} pathname={pathname} />
                ))}
              </>
            )}
          </ul>
        </nav>

        {/* 좁은 화면: ☰ 로 여는 메뉴 */}
        {menuOpen && (
          <div id="mobile-menu" className="max-h-[calc(100vh-4rem)] overflow-y-auto border-t border-navy-100 bg-white md:hidden">
            <div className="px-4 py-3">
              <HeaderSearch className="flex" onDone={() => setMenuOpen(false)} />
              <p className="mt-3 text-sm text-navy-600">
                <b className="text-navy-900">{user.name}</b> 님{roleLabel && ` · ${roleLabel}`}
              </p>
            </div>
            <MobileGroup title="이용" items={userNav} pathname={pathname} />
            {adminNav.length > 0 && <MobileGroup title="관리" items={adminNav} pathname={pathname} />}
            <div className="border-t border-navy-100 px-4 py-3">
              <button type="button" onClick={logout} className={`${btn.secondary} w-full`}>
                로그아웃
              </button>
            </div>
          </div>
        )}
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8">
        {forbidden ? <Forbidden /> : children}
      </main>

      <footer className="no-print mt-8 border-t border-navy-100 bg-navy-50 text-sm text-navy-600">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <p className="flex items-center gap-2 font-bold text-navy-900">
              <Logo size={24} className="rounded" /> {APP_NAME}
            </p>
            <p className="mt-2 leading-relaxed">
              {APP_TAGLINE}입니다. 지도에서 기관을 찾고 물품을 예약해 빌려 쓰세요.
              <br />
              모든 시간은 한국 시간(KST) 기준입니다.
            </p>
          </div>
          <FooterLinks title="이용 안내" items={userNav.filter((n) => n.href !== "/")} />
          {adminNav.length > 0 ? <FooterLinks title="관리" items={adminNav} /> : <div />}
        </div>
        <div className="border-t border-navy-100">
          <p className="mx-auto max-w-6xl px-4 py-4 text-xs text-navy-500">
            © {new Date().getFullYear()} {APP_NAME}. 물품 대여 문의는 각 기관 담당자에게 해 주세요.
          </p>
        </div>
      </footer>
    </div>
  );
}

type NavItem = { href: string; label: string };

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = isActive(pathname, item.href);
  return (
    <li className="shrink-0">
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={`block border-b-[3px] px-3 py-3 font-semibold ${
          active ? "border-teal-600 text-teal-800" : "border-transparent text-navy-700 hover:text-navy-900"
        }`}
      >
        {item.label}
      </Link>
    </li>
  );
}

function MobileGroup({ title, items, pathname }: { title: string; items: NavItem[]; pathname: string }) {
  return (
    <div className="border-t border-navy-100 px-2 py-2">
      <p className="px-2 py-1 text-xs font-bold text-navy-400">{title}</p>
      <ul>
        {items.map((n) => {
          const active = isActive(pathname, n.href);
          return (
            <li key={n.href}>
              <Link
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center justify-between rounded-lg px-3 py-2.5 font-semibold ${
                  active ? "bg-teal-50 text-teal-800" : "text-navy-800 hover:bg-navy-50"
                }`}
              >
                {n.label}
                <span aria-hidden className="text-navy-300">›</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function FooterLinks({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div>
      <p className="font-bold text-navy-900">{title}</p>
      <ul className="mt-2 grid gap-1.5">
        {items.map((n) => (
          <li key={n.href}>
            <Link href={n.href} className="hover:text-navy-900 hover:underline">
              {n.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 머리말 검색: 물품 이름·관리번호로 물품 찾기 화면을 연다 */
function HeaderSearch({ className = "", onDone }: { className?: string; onDone?: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <form
      role="search"
      className={`items-center overflow-hidden rounded-full border border-navy-200 bg-white focus-within:border-teal-600 ${className}`}
      onSubmit={(e) => {
        e.preventDefault();
        const v = q.trim();
        router.push(v ? `/items?q=${encodeURIComponent(v)}` : "/items");
        onDone?.();
      }}
    >
      <label className="sr-only" htmlFor={onDone ? "header-q-m" : "header-q"}>
        물품 검색
      </label>
      <input
        id={onDone ? "header-q-m" : "header-q"}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="물품 이름이나 관리번호 검색"
        className="min-w-0 flex-1 bg-transparent px-4 py-2 text-sm text-navy-900 outline-none placeholder:text-navy-300"
      />
      <button type="submit" className="shrink-0 px-4 py-2 text-sm font-semibold text-teal-800 hover:bg-teal-50">
        검색
      </button>
    </form>
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
