"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { entriesApi, reportsApi } from "@/lib/api";
import { formatJalaliLong, formatRials } from "@/lib/format";

function KpiCard({
  label,
  value,
  hint,
  href,
  tone = "default",
}: {
  label: string;
  value: number;
  hint?: string;
  href?: string;
  tone?: "default" | "good" | "bad";
}) {
  const inner = (
    <div className="card relative overflow-hidden p-4 transition-colors hover:border-primary">
      <span
        className={`absolute inset-y-3 right-0 w-0.5 rounded ${
          tone === "good" ? "bg-success-strong" : tone === "bad" ? "bg-danger-strong" : "bg-primary"
        }`}
        aria-hidden="true"
      />
      <div className="text-xs font-semibold text-muted">{label}</div>
      <div className="mt-2 text-base font-extrabold tabular-nums">
        {formatRials(value)}
        <span className="mr-1 text-[11px] font-semibold text-muted">ریال</span>
      </div>
      {hint ? <div className="mt-2 text-[11px] font-bold text-muted">{hint}</div> : null}
    </div>
  );
  return href ? <Link href={href} className="block focus:outline-none">{inner}</Link> : inner;
}

export default function DashboardClient() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "dashboard"],
    queryFn: () => reportsApi.dashboard(),
  });
  const { data: entries } = useQuery({
    queryKey: ["entries", "recent"],
    queryFn: () => entriesApi.list(),
  });

  const recent = useMemo(() => {
    if (data && data.recent_entries.length > 0) return data.recent_entries;
    // fallback while the report endpoint is unavailable: derive from the entry list
    const posted = (entries ?? []).filter((e) => e.status === "posted").slice(0, 5);
    return posted.map((e) => ({
      id: e.id,
      entry_date: e.entry_date,
      reference: e.reference,
      memo: e.memo,
      total: Math.max(
        e.lines.reduce((s, l) => s + l.debit, 0),
        e.lines.reduce((s, l) => s + l.credit, 0),
      ),
    }));
  }, [entries, data]);

  if (isError) {
    return (
      <div className="card p-6 text-sm text-muted">
        در بارگذاری داشبورد خطایی رخ داد.{" "}
        <button className="font-bold text-primary-strong underline" onClick={() => void refetch()}>
          تلاش دوباره
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">داشبورد</h1>
          <p className="mt-0.5 text-xs text-muted">
            {isLoading
              ? "در حال بارگذاری…"
              : data
                ? `نمای کلی مالی — سال ${data.fiscal_year.toLocaleString("fa-IR")} · تا ${formatJalaliLong(new Date(data.as_of + "T12:00:00"))}`
                : "نمای کلی مالی"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/reports" className="btn btn-ghost">گزارشها</Link>
          <Link href="/journal-entries/new" className="btn btn-primary">+ سند جدید</Link>
        </div>
      </div>

      {isLoading || !data ? (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card h-28 animate-pulse bg-surface-2" />
          ))}
        </div>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="موجودی نقد و بانک" value={data.cash_bank} href="/reports/cash-flow" hint="از دفتر کل (حسابهای ۱۰۱ و ۱۰۲)" />
            <KpiCard
              label="درآمد دوره"
              value={data.revenue}
              href="/reports/profit-loss"
              hint="سال جاری تا امروز"
              tone={data.revenue >= 0 ? "good" : "default"}
            />
            <KpiCard
              label="هزینههای دوره"
              value={data.expenses}
              href="/reports/profit-loss"
              hint="سال جاری تا امروز"
              tone="bad"
            />
            <KpiCard
              label="نتیجه خالص"
              value={data.net_income}
              href="/reports/profit-loss"
              hint={data.net_income >= 0 ? "سودآور" : "زیانده"}
              tone={data.net_income >= 0 ? "good" : "bad"}
            />
          </div>

          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="دریافتنی (مشتریان)"
              value={data.receivables}
              href="/reports/aging"
              hint={`سن مطالبات: ${data.receivable_aging_total.toLocaleString("fa-IR")} ریال`}
            />
            <KpiCard
              label="پرداختنی (تأمینکنندگان)"
              value={data.payables}
              href="/reports/aging"
              hint={`سن بدهیها: ${data.payable_aging_total.toLocaleString("fa-IR")} ریال`}
            />
            <KpiCard
              label="جریان نقد دوره"
              value={data.cash_flow_net}
              href="/reports/cash-flow"
              hint={data.cash_flow_reconciled ? "تطبیق با دفتر کل" : "عدم تطبیق!"}
              tone={data.cash_flow_net >= 0 ? "good" : "bad"}
            />
            <KpiCard
              label="تأمین مالی دوره"
              value={data.funding_total}
              href="/reports/funding"
              hint={data.funding_reconciled ? "تطبیق با دفتر کل" : "عدم تطبیق!"}
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <section className="card">
              <div className="card-head">
                <h2 className="text-sm font-extrabold">آخرین اسناد</h2>
                <span className="mr-auto">
                  <Link href="/transactions" className="text-[11px] font-bold text-primary-strong underline">
                    همه سندها
                  </Link>
                </span>
              </div>
              {recent.length === 0 ? (
                <div className="px-4 py-6 text-sm text-muted">
                  هنوز سندی ثبت نشده است.{" "}
                  <Link href="/journal-entries/new" className="font-bold text-primary-strong underline">
                    اولین سند را ثبت کنید
                  </Link>
                </div>
              ) : (
                <div className="divide-y divide-dashed divide-border px-4 py-2 text-sm">
                  {recent.map((e) => (
                    <div key={e.id} className="flex items-center justify-between gap-2 py-2.5">
                      <div className="min-w-0">
                        <div className="truncate font-semibold">{e.memo}</div>
                        <div className="text-[11px] text-muted">
                          {e.reference ? <span dir="ltr">{e.reference}</span> : "پیشنویس"} ·{" "}
                          {formatJalaliLong(new Date(e.entry_date + "T12:00:00"))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-success-soft px-2 py-0.5 text-[10px] font-bold text-success-strong">
                          ثبتشده
                        </span>
                        <span className="font-bold tabular-nums">{formatRials(e.total)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="card">
              <div className="card-head">
                <h2 className="text-sm font-extrabold">حسابهای کلیدی</h2>
                <span className="text-[11px] text-muted">از دفتر کل (سندهای ثبتشده)</span>
              </div>
              {data.key_accounts.length === 0 ? (
                <div className="px-4 py-6 text-sm text-muted">
                  هنوز سند ثبتشدهای نیست. با «سند افتتاحیه» شروع کنید (راهنمای استفاده).
                </div>
              ) : (
                <div className="divide-y divide-dashed divide-border px-4">
                  {data.key_accounts.map((b) => (
                    <Link
                      key={b.code}
                      href={`/reports/general-ledger?account_code=${b.code}`}
                      className="flex items-center gap-2 py-2 text-sm transition-colors hover:bg-surface-2"
                    >
                      <span className="font-bold tabular-nums" dir="ltr">{b.code}</span>
                      <span className="min-w-0 flex-1 truncate">{b.name}</span>
                      <span className={`font-bold tabular-nums ${b.balance < 0 ? "text-danger-strong" : ""}`}>
                        {formatRials(b.balance)}
                      </span>
                      <span className="text-[11px] text-muted">ریال</span>
                    </Link>
                  ))}
                </div>
              )}
              <div className="flex items-center justify-between border-t border-border px-4 py-2">
                <Link href="/guide#journey-entry" className="text-[11px] font-bold text-primary-strong underline">
                  راهنمای ثبت سند
                </Link>
                <Link href="/reports/trial-balance" className="text-[11px] font-bold text-primary-strong underline">
                  تراز آزمایشی
                </Link>
              </div>
            </section>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {data.budget_utilization !== null && data.total_budget > 0 && (
              <span className="rounded-full bg-surface-2 px-3 py-1 text-[11px] font-bold text-muted">
                مصرف بودجه پروژهها:{" "}
                <b className="tabular-nums">{(Math.round(data.budget_utilization * 100)).toLocaleString("fa-IR")}٪</b>{" "}
                ({formatRials(data.total_actual)} از {formatRials(data.total_budget)} ریال)
              </span>
            )}
            <span className="rounded-full bg-surface-2 px-3 py-1 text-[11px] font-bold text-muted">
              تطبیق سن مطالبات/بدهیها:{" "}
              {data.aging_reconciled ? (
                <b className="text-success-strong">برقرار</b>
              ) : (
                <b className="text-danger-strong">ناقص</b>
              )}
            </span>
          </div>

          <p className="mt-4 rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
            <b className="text-text">یادداشت:</b> همه کارتهای داشبورد از گزارشهای مالی محاسبه
            میشوند که مستقیماً از دفتر کل (سندهای ثبتشده) ساخته میشوند؛ ارقام نمونه طراحی دیگر
            وجود ندارند. با کلیک روی هر کارت به گزارش مربوطه میروید.
          </p>
        </>
      )}
    </div>
  );
}
