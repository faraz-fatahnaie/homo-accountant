"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { authApi, clearTokens, getTokens, type UserOut } from "@/lib/api";
import { useTheme } from "@/lib/theme";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  available: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "داشبورد", icon: "M4 5h16l-6.2 7.4V19l-3.6-1.8v-4.8z", available: true },
  { href: "/transactions", label: "تراکنشها", icon: "M8 3l-5 5 5 5M3 8h18M16 21l5-5-5-5M21 16H3", available: false },
  { href: "/expenses/new", label: "ثبت هزینه", icon: "M12 5v14M5 12h14", available: false },
  { href: "/invoices", label: "صورتحسابها", icon: "M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7zM14 2v5h5", available: false },
];

function Icon({ d, className }: { d: string; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className ?? "h-4 w-4"}
    >
      <path d={d} />
    </svg>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const [user, setUser] = useState<UserOut | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!getTokens().access) {
      router.replace("/login");
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        clearTokens();
        router.replace("/login");
      });
  }, [router]);

  function logout() {
    const { refresh } = getTokens();
    if (refresh) void authApi.logout(refresh).catch(() => undefined);
    clearTokens();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen" dir="rtl">
      {/* Sidebar (desktop) */}
      <aside className="fixed inset-y-0 right-0 hidden w-56 flex-col border-l border-[var(--sb-border)] bg-[var(--sb-bg)] text-[var(--sb-text)] lg:flex">
        <div className="flex items-center gap-2.5 px-4 py-3.5">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-primary font-extrabold text-on-primary">
            آ
          </div>
          <div>
            <div className="text-sm font-extrabold">آریا تجارت</div>
            <div className="text-[10px] text-[var(--sb-muted)]">سامانه حسابداری</div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            return item.available ? (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded px-2.5 py-2 text-[13px] font-semibold ${
                  active
                    ? "bg-[var(--sb-active)] text-[var(--sb-active-text)]"
                    : "hover:bg-[var(--sb-hover)]"
                }`}
              >
                <Icon d={item.icon} className="h-4 w-4 text-[var(--sb-muted)]" />
                {item.label}
              </Link>
            ) : (
              <span
                key={item.href}
                title="در نسخههای بعدی"
                className="flex cursor-not-allowed items-center gap-2.5 rounded px-2.5 py-2 text-[13px] font-semibold opacity-60"
              >
                <Icon d={item.icon} className="h-4 w-4 text-[var(--sb-muted)]" />
                {item.label}
                <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <rect x="4" y="11" width="16" height="10" rx="2" />
                  <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                </svg>
              </span>
            );
          })}
        </nav>
        <div className="border-t border-[var(--sb-border)] p-2.5">
          <div className="flex items-center gap-2 rounded bg-[var(--sb-hover)] p-2">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-primary text-xs font-bold text-on-primary">
              {user ? user.full_name.slice(0, 2) : "—"}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-bold">{user?.full_name ?? "…"}</div>
              <div className="text-[10px] text-[var(--sb-muted)]">
                {mounted ? (user ? roleLabel(user.role) : "در حال بارگذاری") : ""}
              </div>
            </div>
            <button onClick={logout} aria-label="خروج از حساب" className="text-[var(--sb-muted)] hover:text-white">
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="lg:mr-56">
        {/* Topbar */}
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-[var(--topbar-bg)] px-4 py-2.5">
          <div className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-muted flex-1 max-w-md">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <circle cx="11" cy="11" r="7" />
              <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              placeholder="جستجوی تراکنش، طرف حساب، شماره سند…"
              aria-label="جستجو"
              className="w-full bg-transparent text-sm outline-none"
            />
            <kbd className="rounded border border-border bg-surface px-1.5 text-[10px]" dir="ltr">
              /
            </kbd>
          </div>
          <div className="flex-1" />
          {/* Mobile user chip (sidebar is hidden on small screens) */}
          <div className="flex items-center gap-1.5 rounded-md border border-border bg-surface px-1.5 py-1 lg:hidden">
            <div className="grid h-6 w-6 place-items-center rounded-full bg-primary text-[10px] font-bold text-on-primary">
              {user ? user.full_name.slice(0, 2) : "—"}
            </div>
            <span className="text-[11px] font-bold">{mounted && user ? roleLabel(user.role) : ""}</span>
          </div>
          <button onClick={toggleTheme} aria-label={theme === "dark" ? "حالت روشن" : "حالت تیره"} className="grid h-8 w-8 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text">
            {mounted && theme === "dark" ? (
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8}>
                <circle cx="12" cy="12" r="4.2" />
                <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6" strokeLinecap="round" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinejoin="round">
                <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
              </svg>
            )}
          </button>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-5 pb-24 lg:px-6 lg:pb-10">{children}</main>
      </div>

      {/* Bottom nav (mobile) */}
      <nav className="fixed bottom-0 right-0 left-0 z-30 flex h-14 border-t border-border bg-surface lg:hidden" aria-label="ناوبری موبایل">
        {NAV_ITEMS.map((item) => {
          const active = pathname.startsWith(item.href);
          return item.available ? (
            <Link key={item.href} href={item.href} className={`flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] font-bold ${active ? "text-primary-strong" : "text-muted"}`}>
              <Icon d={item.icon} className="h-5 w-5" />
              {item.label}
            </Link>
          ) : (
            <span key={item.href} className="flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] font-bold text-muted opacity-60" title="در نسخههای بعدی">
              <Icon d={item.icon} className="h-5 w-5" />
              {item.label}
            </span>
          );
        })}
      </nav>
    </div>
  );
}

function roleLabel(role: UserOut["role"]): string {
  const map: Record<UserOut["role"], string> = {
    owner: "مدیر",
    accountant: "حسابدار",
    staff: "کارمند",
    viewer: "بیننده",
  };
  return map[role] ?? role;
}
