"use client";

import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api";
import { ErrorBlock, LoadingBlock } from "@/components/ui";
import { formatJalali } from "@/lib/format";

/** Reconciliation panel on the reports hub: cross-check summary + each check. */
export function ReconciliationPanel() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "reconciliation"],
    queryFn: () => reportsApi.reconciliation(),
  });

  if (isLoading) return <LoadingBlock label="در حال تطبیق ارقام…" />;
  if (isError)
    return <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />;
  if (!data) return null;

  return (
    <section className="card" aria-label="تطبیق با دفتر کل">
      <div className="card-head">
        <h2 className="text-sm font-extrabold">تطبیق گزارشها با دفتر کل</h2>
        <span className="mr-auto text-[11px] text-muted">
          تا تاریخ {formatJalali(new Date(data.as_of + "T12:00:00"))}
        </span>
      </div>
      <div className={`flex items-center gap-2 px-4 py-3 text-sm font-bold ${data.all_ok ? "text-success-strong" : "text-danger-strong"}`}>
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${data.all_ok ? "bg-success-strong" : "bg-danger-strong"}`}
          aria-hidden="true"
        />
        {data.all_ok
          ? "همه بررسیها موفق — ارقام با دفتر کل منطبقاند"
          : "برخی بررسیها ناموفقاند — برای جزئیات به زیر مراجعه کنید"}
      </div>
      <ul className="divide-y divide-dashed divide-border border-t border-border px-4 text-sm">
        {data.checks.map((c) => (
          <li key={c.key} className="flex items-center justify-between gap-3 py-2.5">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className={`grid h-5 w-5 flex-none place-items-center rounded-full text-[11px] font-bold text-on-primary ${
                  c.ok ? "bg-success-strong" : "bg-danger-strong"
                }`}
                aria-hidden="true"
              >
                {c.ok ? "✓" : "!"}
              </span>
              <span className="truncate font-semibold">{c.label}</span>
            </div>
            <span className="flex-none text-[11px] tabular-nums text-muted" dir="rtl">
              {c.detail}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
