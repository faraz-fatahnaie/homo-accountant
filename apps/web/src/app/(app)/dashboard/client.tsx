"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { entriesApi } from "@/lib/api";
import { formatJalaliLong, formatRials } from "@/lib/format";
import { StatusBadge } from "@/components/ui";

const KPIS = [
  { label: "موجودی نقد و بانک", value: "۱۸۴٬۶۲۰٬۰۰۰", delta: "+۴٬۲۱۰٬۰۰۰ نسبت به تیر" },
  { label: "درآمد دوره", value: "۹۶٬۸۵۰٬۰۰۰", delta: "۱۲٪ نسبت به سه ماه قبل" },
  { label: "هزینههای دوره", value: "۶۱٬۳۴۰٬۰۰۰", delta: "۳٪ کاهش نسبت به سه ماه قبل" },
  { label: "نتیجه خالص", value: "۳۵٬۵۱۰٬۰۰۰", delta: "سودآور" },
];

export default function DashboardClient() {
  const { data: entries, isLoading } = useQuery({
    queryKey: ["entries", "recent"],
    queryFn: () => entriesApi.list(),
  });
  const recent = (entries ?? []).slice(0, 5);

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

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KPIS.map((kpi) => (
          <div key={kpi.label} className="card relative overflow-hidden p-4">
            <span className="absolute inset-y-3 right-0 w-0.5 rounded bg-primary" aria-hidden="true" />
            <div className="text-xs font-semibold text-muted">{kpi.label}</div>
            <div className="mt-2 text-base font-extrabold tabular-nums">
              {kpi.value}
              <span className="mr-1 text-[11px] font-semibold text-muted">ریال</span>
            </div>
            <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-border bg-success-soft px-2 py-0.5 text-[11px] font-bold text-success-strong">
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
          {isLoading ? (
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
            <h2 className="text-sm font-extrabold">دسترسی سریع</h2>
          </div>
          <div className="grid grid-cols-2 gap-2 p-4 text-sm">
            <Link href="/transactions" className="rounded-md border border-border bg-surface-2 px-3 py-2.5 font-bold hover:bg-surface">
              سندها و تراکنشها
            </Link>
            <Link href="/accounts" className="rounded-md border border-border bg-surface-2 px-3 py-2.5 font-bold hover:bg-surface">
              حسابها (کدینگ)
            </Link>
            <Link href="/periods" className="rounded-md border border-border bg-surface-2 px-3 py-2.5 font-bold hover:bg-surface">
              دورههای حسابداری
            </Link>
            <span className="cursor-not-allowed rounded-md border border-dashed border-border px-3 py-2.5 font-bold text-muted opacity-70" title="در نسخههای بعدی">
              گزارشها
            </span>
          </div>
        </section>
      </div>

      <p className="mt-6 rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
        <b className="text-text">یادداشت:</b> کارتهای بالا (موجودی، درآمد، هزینه، نتیجه) نمونه طراحی
        هستند و از اسلایس ۸ (گزارشها) مستقیماً از دفتر کل محاسبه میشوند. فهرست «آخرین اسناد» از داده
        واقعی سامانه است.
      </p>
    </div>
  );
}
