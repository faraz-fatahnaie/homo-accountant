"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { accountsApi, entriesApi, type AccountBalanceOut } from "@/lib/api";
import { formatJalaliLong, formatRials } from "@/lib/format";
import { StatusBadge } from "@/components/ui";

/** KPI cards that are still design samples (become real in slice 8). */
const SAMPLE_KPIS = [
  { label: "درآمد دوره", value: "۹۶٬۸۵۰٬۰۰۰", delta: "۱۲٪ نسبت به سه ماه قبل (نمونه)" },
  { label: "هزینههای دوره", value: "۶۱٬۳۴۰٬۰۰۰", delta: "۳٪ کاهش (نمونه)" },
  { label: "نتیجه خالص", value: "۳۵٬۵۱۰٬۰۰۰", delta: "سودآور (نمونه)" },
];

function BalanceRow({ b }: { b: AccountBalanceOut }) {
  return (
    <div className="flex items-center gap-2 py-2 text-sm">
      <span className="font-bold tabular-nums" dir="ltr">{b.code}</span>
      <span className="min-w-0 flex-1 truncate">{b.name}</span>
      <span className={`font-bold tabular-nums ${b.balance < 0 ? "text-danger-strong" : ""}`}>
        {formatRials(b.balance)}
      </span>
      <span className="text-[11px] text-muted">ریال</span>
    </div>
  );
}

export default function DashboardClient() {
  const { data: entries, isLoading: entriesLoading } = useQuery({
    queryKey: ["entries", "recent"],
    queryFn: () => entriesApi.list(),
  });
  const { data: balances, isLoading: balancesLoading } = useQuery({
    queryKey: ["balances"],
    queryFn: accountsApi.balances,
  });

  const recent = (entries ?? []).slice(0, 5);

  // موجودی نقد و بانک = مانده حسابهای ۱۰۱ (صندوق) + ۱۰۲ (بانک) — از دفتر کل
  const cashAndBank = useMemo(
    () =>
      (balances ?? [])
        .filter((b) => b.code === "101" || b.code === "102")
        .reduce((s, b) => s + b.balance, 0),
    [balances],
  );

  // مهمترین حسابهای دارای مانده (مرتب بر اساس قدرمطلق مانده)
  const keyAccounts = useMemo(
    () =>
      (balances ?? [])
        .filter((b) => b.balance !== 0 && ["101", "102", "203", "204", "301", "401", "402"].includes(b.code))
        .sort((a, b) => Math.abs(b.balance) - Math.abs(a.balance))
        .slice(0, 6),
    [balances],
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">داشبورد</h1>
          <p className="mt-0.5 text-xs text-muted">نمای کلی مالی — سال ۱۴۰۵</p>
        </div>
        <Link href="/journal-entries/new" className="btn btn-primary">
          + سند جدید
        </Link>
      </div>

      {/* Cash & bank — real, computed from the posted ledger */}
      <div className="mb-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="card relative overflow-hidden border-2 border-primary p-4 lg:col-span-1">
          <span className="absolute inset-y-3 right-0 w-1 rounded bg-primary" aria-hidden="true" />
          <div className="text-xs font-semibold text-muted">موجودی نقد و بانک</div>
          <div className="mt-2 text-xl font-extrabold tabular-nums">
            {balancesLoading ? "…" : formatRials(cashAndBank)}
            <span className="mr-1 text-[11px] font-semibold text-muted">ریال</span>
          </div>
          <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-bold text-primary-strong">
            از دفتر کل (حسابهای ۱۰۱ و ۱۰۲)
          </div>
        </div>
        {SAMPLE_KPIS.map((kpi) => (
          <div key={kpi.label} className="card relative overflow-hidden p-4">
            <span className="absolute inset-y-3 right-0 w-0.5 rounded bg-primary" aria-hidden="true" />
            <div className="text-xs font-semibold text-muted">{kpi.label}</div>
            <div className="mt-2 text-base font-extrabold tabular-nums">
              {kpi.value}
              <span className="mr-1 text-[11px] font-semibold text-muted">ریال</span>
            </div>
            <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-[11px] font-bold text-muted">
              {kpi.delta}
            </div>
          </div>
        ))}
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
          {entriesLoading ? (
            <div className="px-4 py-6 text-sm text-muted">در حال بارگذاری…</div>
          ) : recent.length === 0 ? (
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
                    <StatusBadge status={e.status} />
                    <span className="font-bold tabular-nums">
                      {formatRials(Math.max(e.lines.reduce((s, l) => s + l.debit, 0), e.lines.reduce((s, l) => s + l.credit, 0)))}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="card">
          <div className="card-head">
            <h2 className="text-sm font-extrabold">مانده حسابهای کلیدی</h2>
            <span className="text-[11px] text-muted">از دفتر کل (سندهای ثبتشده)</span>
          </div>
          {balancesLoading ? (
            <div className="px-4 py-6 text-sm text-muted">در حال بارگذاری…</div>
          ) : keyAccounts.length === 0 ? (
            <div className="px-4 py-6 text-sm text-muted">
              هنوز سند ثبتشدهای نیست. با «سند افتتاحیه» شروع کنید (راهنمای استفاده).
            </div>
          ) : (
            <div className="divide-y divide-dashed divide-border px-4">
              {keyAccounts.map((b) => (
                <BalanceRow key={b.code} b={b} />
              ))}
            </div>
          )}
          <div className="border-t border-border px-4 py-2">
            <Link href="/guide#journey-entry" className="text-[11px] font-bold text-primary-strong underline">
              راهنمای ثبت سند
            </Link>
          </div>
        </section>
      </div>

      <p className="mt-6 rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
        <b className="text-text">یادداشت:</b> «موجودی نقد و بانک» و «مانده حسابهای کلیدی» مستقیماً از
        دفتر کل محاسبه میشوند. کارتهای درآمد/هزینه/نتیجه هنوز نمونه طراحی هستند و از اسلایس ۸
        (گزارشها) واقعی میشوند.
      </p>
    </div>
  );
}
