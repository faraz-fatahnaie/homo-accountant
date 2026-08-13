"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fundingApi, FUNDING_TYPE_LABELS, type FundingType } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalaliLong, formatRials } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

const TYPE_TONES: Record<FundingType, "info" | "warn" | "success" | "muted"> = {
  investment: "info",
  loan: "warn",
  grant: "success",
  revenue: "muted",
};

export default function FundingPage() {
  const { isWriter } = useAuth();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["funding"],
    queryFn: fundingApi.list,
  });
  const { data: mappings } = useQuery({ queryKey: ["funding-mappings"], queryFn: fundingApi.mappings });

  const totals = useMemo(() => {
    const list = data ?? [];
    const byType = new Map<FundingType, number>();
    for (const t of Object.keys(FUNDING_TYPE_LABELS) as FundingType[]) byType.set(t, 0);
    for (const e of list) byType.set(e.funding_type, (byType.get(e.funding_type) ?? 0) + e.amount);
    return {
      count: list.length,
      byType,
      total: list.reduce((s, e) => s + e.amount, 0),
    };
  }, [data]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">تأمین مالی</h1>
          <p className="mt-0.5 text-xs text-muted">
            سرمایهگذاری، وام، کمک و درآمد — {totals.count} رویداد · جمع{" "}
            <b className="tabular-nums">{formatRials(totals.total)}</b> ریال
          </p>
        </div>
        {isWriter ? (
          <Link href="/funding/new" className="btn btn-primary">+ رویداد تأمین مالی</Link>
        ) : null}
      </div>

      {/* summary by type */}
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {(Object.keys(FUNDING_TYPE_LABELS) as FundingType[]).map((t) => (
          <div key={t} className="card p-3">
            <div className="text-xs font-semibold text-muted">{FUNDING_TYPE_LABELS[t]}</div>
            <div className="mt-1 text-sm font-extrabold tabular-nums">{formatRials(totals.byType.get(t) ?? 0)}</div>
          </div>
        ))}
      </div>

      {mappings && mappings.length > 0 ? (
        <p className="mb-3 text-[11px] text-muted">
          نگاشت حسابها:{" "}
          {mappings.map((m) => (
            <span key={m.funding_type} className="ml-2 inline-flex items-center gap-1">
              <b>{FUNDING_TYPE_LABELS[m.funding_type]}</b>
              <span dir="ltr">{m.account_code}</span>
            </span>
          ))}
        </p>
      ) : null}

      {isLoading ? <LoadingBlock /> : null}
      {isError ? <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} /> : null}

      {data && data.length === 0 ? (
        <div className="card px-4 py-10 text-center text-sm text-muted">
          هنوز رویداد تأمین مالی ثبت نشده است.
        </div>
      ) : null}

      {data && data.length > 0 ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-right text-sm">
              <thead>
                <tr className="border-b-2 border-border-strong bg-surface-2 text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2.5">شماره</th>
                  <th className="px-3 py-2.5">نوع</th>
                  <th className="px-3 py-2.5">طرف حساب</th>
                  <th className="px-3 py-2.5">تاریخ</th>
                  <th className="px-3 py-2.5">مرجع/توافق</th>
                  <th className="px-3 py-2.5 text-left">مبلغ (ریال)</th>
                  <th className="px-3 py-2.5">روش</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {data.map((e) => (
                  <tr key={e.id} className="hover:bg-[var(--row-hover)]">
                    <td className="px-3 py-2.5 font-bold" dir="ltr">{e.number}</td>
                    <td className="px-3 py-2.5"><Badge tone={TYPE_TONES[e.funding_type]}>{FUNDING_TYPE_LABELS[e.funding_type]}</Badge></td>
                    <td className="px-3 py-2.5 max-w-[160px] truncate">{e.contact_name || "—"}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-xs text-muted">
                      {formatJalaliLong(new Date(e.event_date + "T12:00:00"))}
                      {e.maturity_date ? <div className="text-[10px]">سررسید: {formatJalaliLong(new Date(e.maturity_date + "T12:00:00"))}</div> : null}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted" dir="ltr">{e.agreement_ref ?? "—"}</td>
                    <td className="px-3 py-2.5 text-left font-bold tabular-nums">{formatRials(e.amount)}</td>
                    <td className="px-3 py-2.5 text-xs text-muted">
                      {e.method === "cash" ? "نقدی" : e.method === "bank" ? "انتقال بانکی" : "آنلاین"}
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
