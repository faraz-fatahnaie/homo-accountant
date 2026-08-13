"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { entriesApi, type JournalEntryOut } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { FA_MONTHS, formatJalaliLong, formatRials, todayJalali } from "@/lib/format";
import { EmptyBlock, ErrorBlock, LoadingBlock, StatusBadge } from "@/components/ui";

function entryTotal(e: JournalEntryOut): number {
  return Math.max(
    e.lines.reduce((s, l) => s + l.debit, 0),
    e.lines.reduce((s, l) => s + l.credit, 0),
  );
}

export default function TransactionsPage() {
  const { isWriter } = useAuth();
  const queryClient = useQueryClient();
  const today = todayJalali();
  const [periodMonth, setPeriodMonth] = useState<number>(today[1]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["entries", { period_year: today[0], period_month: periodMonth }],
    queryFn: () =>
      entriesApi.list({ period_year: today[0], period_month: periodMonth }),
  });

  const postMutation = useMutation({
    mutationFn: (id: number) => entriesApi.post(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
  });

  const voidMutation = useMutation({
    mutationFn: (id: number) => entriesApi.voidEntry(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
  });

  const totals = useMemo(() => {
    const list = data ?? [];
    const posted = list.filter((e) => e.status === "posted");
    return {
      count: list.length,
      postedCount: posted.length,
      sum: list.reduce((s, e) => s + entryTotal(e), 0),
    };
  }, [data]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">سندهای حسابداری</h1>
          <p className="mt-0.5 text-xs text-muted">
            {totals.count} سند · {totals.postedCount} ثبتشده · جمع مبلغ{" "}
            <b className="tabular-nums">{formatRials(totals.sum)}</b> ریال
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold text-muted" htmlFor="period-month">
            دوره (ماه شمسی)
          </label>
          <select
            id="period-month"
            className="input w-auto"
            value={periodMonth}
            onChange={(e) => setPeriodMonth(Number(e.target.value))}
          >
            {FA_MONTHS.map((m, i) => (
              <option key={m} value={i + 1}>
                {m} {formatRials(today[0])}
              </option>
            ))}
          </select>
          {isWriter ? (
            <Link href="/journal-entries/new" className="btn btn-primary">
              + سند جدید
            </Link>
          ) : null}
        </div>
      </div>

      {isLoading ? <LoadingBlock /> : null}
      {isError ? (
        <ErrorBlock
          message={error instanceof Error ? error.message : "خطای ناشناخته"}
          onRetry={() => void refetch()}
        />
      ) : null}

      {data && data.length === 0 ? (
        <EmptyBlock
          title="سندی در این دوره یافت نشد"
          {...(isWriter ? { hint: "با دکمه «سند جدید» اولین سند را ثبت کنید." } : {})}
        />
      ) : null}

      {data && data.length > 0 ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-right text-sm">
              <thead>
                <tr className="border-b-2 border-border-strong bg-surface-2 text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2.5">تاریخ</th>
                  <th className="px-3 py-2.5">شماره</th>
                  <th className="px-3 py-2.5">شرح</th>
                  <th className="px-3 py-2.5">حسابها</th>
                  <th className="px-3 py-2.5 text-left">مبلغ (ریال)</th>
                  <th className="px-3 py-2.5">وضعیت</th>
                  <th className="px-3 py-2.5">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {data.map((entry) => (
                  <tr key={entry.id} className="hover:bg-[var(--row-hover)]">
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {formatJalaliLong(new Date(entry.entry_date + "T12:00:00"))}
                    </td>
                    <td className="px-3 py-2.5 font-bold" dir="ltr">
                      {entry.reference ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 max-w-[240px] truncate">{entry.memo}</td>
                    <td className="px-3 py-2.5 max-w-[200px] truncate text-xs text-muted">
                      {entry.lines.map((l) => l.account_name).join("، ")}
                    </td>
                    <td className="px-3 py-2.5 text-left font-bold tabular-nums">
                      {formatRials(entryTotal(entry))}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge status={entry.status} />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-1">
                        {entry.status === "draft" && isWriter ? (
                          <button
                            className="btn btn-ghost btn-sm"
                            disabled={postMutation.isPending}
                            onClick={() => postMutation.mutate(entry.id)}
                          >
                            ثبت نهایی
                          </button>
                        ) : null}
                        {entry.status === "posted" && isWriter && entry.reversal_of_id === null ? (
                          <button
                            className="btn btn-danger-ghost btn-sm"
                            disabled={voidMutation.isPending}
                            onClick={() => {
                              if (window.confirm("سند برگشتی (معکوس) برای این سند ثبت میشود. ادامه میدهید؟"))
                                voidMutation.mutate(entry.id);
                            }}
                          >
                            برگشت
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
