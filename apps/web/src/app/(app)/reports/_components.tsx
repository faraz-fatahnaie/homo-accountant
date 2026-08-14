"use client";

import Link from "next/link";
import { useState } from "react";
import { formatJalali, formatRials, jalaliToGregorian, parseJalaliInput, todayJalali } from "@/lib/format";

/** First day of the current Solar Hijri fiscal year (۱ فروردین). */
export function fiscalYearStart(): Date {
  const [jy] = todayJalali();
  return jalaliToGregorian(jy, 1, 1);
}

export function today(): Date {
  const [jy, jm, jd] = todayJalali();
  return jalaliToGregorian(jy, jm, jd);
}

/** Sub-navigation shared by every report page. */
const REPORT_LINKS = [
  { href: "/reports/trial-balance", label: "تراز آزمایشی" },
  { href: "/reports/balance-sheet", label: "ترازنامه" },
  { href: "/reports/profit-loss", label: "سود و زیان" },
  { href: "/reports/cash-flow", label: "جریان نقد" },
  { href: "/reports/general-ledger", label: "دفتر کل" },
  { href: "/reports/aging", label: "سررسید" },
  { href: "/reports/budget", label: "بودجه و عملکرد" },
  { href: "/reports/funding", label: "تأمین مالی" },
];

export function ReportTabs({ active }: { active: string }) {
  return (
    <nav aria-label="گزارشها" className="mb-4 flex flex-wrap gap-1.5">
      {REPORT_LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          aria-current={active === l.href ? "page" : undefined}
          className={`rounded-md px-2.5 py-1.5 text-xs font-bold transition-colors ${
            active === l.href
              ? "bg-primary text-on-primary"
              : "border border-border bg-surface-2 text-muted hover:bg-surface"
          }`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}

export function ReportHeader({
  title,
  subtitle,
  active,
  children,
}: {
  title: string;
  subtitle: string;
  active: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">{title}</h1>
          <p className="mt-0.5 text-xs text-muted">{subtitle}</p>
        </div>
        {children}
      </div>
      <div className="mt-3">
        <ReportTabs active={active} />
      </div>
    </div>
  );
}

/** Reconciled vs not badge — every report asserts its ledger invariant. */
export function ReconBadge({ ok, label }: { ok: boolean; label?: string }) {
  return ok ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-0.5 text-[11px] font-bold text-success-strong">
      <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
        <path d="M5 13l4 4L19 7" />
      </svg>
      {label ?? "تطبیق با دفتر کل"}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-danger-soft px-2 py-0.5 text-[11px] font-bold text-danger-strong">
      <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
      {label ?? "عدم تطبیق با دفتر کل"}
    </span>
  );
}

/** Jalali date input; emits ISO Gregorian or null. */
export function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Date;
  onChange: (d: Date) => void;
}) {
  const [text, setText] = useState(() => formatJalali(value));
  return (
    <label className="flex items-center gap-2 text-xs font-bold text-muted">
      {label}
      <input
        className="input w-36"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          const parsed = parseJalaliInput(e.target.value);
          if (parsed) onChange(parsed);
        }}
        onBlur={() => setText(formatJalali(value))}
        dir="ltr"
        inputMode="numeric"
      />
    </label>
  );
}

export function AsOfPicker({
  value,
  onChange,
}: {
  value: Date;
  onChange: (d: Date) => void;
}) {
  return <DateField label="تا تاریخ" value={value} onChange={onChange} />;
}

export function RangePicker({
  from,
  to,
  onChange,
}: {
  from: Date;
  to: Date;
  onChange: (from: Date, to: Date) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <DateField label="از تاریخ" value={from} onChange={(d) => onChange(d, to)} />
      <DateField label="تا تاریخ" value={to} onChange={(d) => onChange(from, d)} />
    </div>
  );
}

export function Money({ value, className }: { value: number; className?: string }) {
  return (
    <span className={`tabular-nums ${value < 0 ? "text-danger-strong" : ""} ${className ?? ""}`}>
      {formatRials(value)}
    </span>
  );
}

export function ReportTable({
  head,
  children,
  label = "جدول گزارش",
}: {
  head: React.ReactNode;
  children: React.ReactNode;
  label?: string;
}) {
  return (
    <div
      className="overflow-x-auto rounded-lg border border-border bg-surface"
      role="region"
      aria-label={label}
      tabIndex={0}
    >
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2 text-[11px] font-bold text-muted">
            {head}
          </tr>
        </thead>
        <tbody className="divide-y divide-dashed divide-border">{children}</tbody>
      </table>
    </div>
  );
}

export function Th({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <th className={`px-3 py-2 text-right font-bold ${className ?? ""}`}>{children}</th>;
}

export function Td({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2 align-middle ${className ?? ""}`}>{children}</td>;
}

export function TotalRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-md bg-surface-2 px-3 py-2 text-sm">
      <span className="font-extrabold">{label}</span>
      <span className="flex items-baseline gap-1.5">
        <b className="tabular-nums">{formatRials(value)}</b>
        <span className="text-[11px] font-semibold text-muted">{hint ?? "ریال"}</span>
      </span>
    </div>
  );
}
