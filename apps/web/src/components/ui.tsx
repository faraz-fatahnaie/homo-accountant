"use client";

import type { ReactNode } from "react";
import { faDigits } from "@/lib/format";
import type { JournalStatus } from "@/lib/api";

export function LoadingBlock({ label = "در حال بارگذاری…" }: { label?: string }) {
  return (
    <div className="card flex items-center justify-center gap-2 px-4 py-10 text-sm text-muted" role="status">
      <svg viewBox="0 0 24 24" className="h-4 w-4 animate-spin" fill="none" stroke="currentColor" strokeWidth={2}>
        <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
      </svg>
      {label}
    </div>
  );
}

export function ErrorBlock({
  message,
  title = "خطا در انجام عملیات",
  onRetry,
}: {
  message: string;
  title?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="card border-danger-soft bg-danger-soft px-4 py-4 text-sm" role="alert">
      <div className="flex items-center gap-2 font-bold text-danger-strong">
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M12 3.5l10 17H2zM12 10v4.5M12 17.6v.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {title}
      </div>
      <p className="mt-1 text-muted">{message}</p>
      {onRetry ? (
        <button className="btn btn-ghost btn-sm mt-2" onClick={onRetry}>
          تلاش دوباره
        </button>
      ) : null}
    </div>
  );
}

export function EmptyBlock({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card px-4 py-12 text-center">
      <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-xl bg-surface-2 text-muted">
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.6}>
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
        </svg>
      </div>
      <h3 className="text-sm font-extrabold">{title}</h3>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export function StatusBadge({ status }: { status: JournalStatus }) {
  if (status === "posted") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2.5 py-0.5 text-[11px] font-bold text-success-strong">
        <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        ثبت‌شده
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] font-bold text-muted">
      پیش‌نویس
    </span>
  );
}

export function Rials({ value, className }: { value: number; className?: string }) {
  return (
    <span className={className ?? ""}>
      {faDigits(value.toLocaleString("en-US").replace(/,/g, "٬"))}
    </span>
  );
}

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "success" | "warn" | "danger" | "info" }) {
  const map = {
    muted: "bg-surface-2 text-muted",
    success: "bg-success-soft text-success-strong",
    warn: "bg-warning-soft text-warning-strong",
    danger: "bg-danger-soft text-danger-strong",
    info: "bg-primary-soft text-primary-strong",
  } as const;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold ${map[tone]}`}>
      {children}
    </span>
  );
}
