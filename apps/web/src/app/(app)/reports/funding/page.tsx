"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { reportsApi } from "@/lib/api";
import { ErrorBlock, LoadingBlock } from "@/components/ui";
import { formatJalaliLong } from "@/lib/format";
import {
  Money,
  RangePicker,
  ReconBadge,
  ReportHeader,
  ReportTable,
  Td,
  Th,
  TotalRow,
  fiscalYearStart,
  today,
} from "../_components";

const TYPE_LABELS: Record<string, string> = {
  investment: "سرمایهگذاری",
  loan: "وام",
  grant: "کمک بلاعوض",
  revenue: "درآمد",
};

export default function FundingPage() {
  const [range, setRange] = useState(() => ({ from: fiscalYearStart(), to: today() }));
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "funding-summary", range.from.toISOString(), range.to.toISOString()],
    queryFn: () => reportsApi.fundingSummary(range.from, range.to),
  });

  return (
    <div>
      <ReportHeader
        active="/reports/funding"
        title="خلاصه تأمین مالی"
        subtitle="رویدادهای سرمایهگذاری، وام، کمک بلاعوض و درآمد در بازه انتخابی."
      >
        <div className="flex flex-wrap items-center gap-2">
          {data && <ReconBadge ok={data.reconciled} label={data.reconciled ? "تطبیق با دفتر کل" : "عدم تطبیق"} />}
          <RangePicker from={range.from} to={range.to} onChange={(from, to) => setRange({ from, to })} />
        </div>
      </ReportHeader>

      {isLoading ? (
        <LoadingBlock />
      ) : isError ? (
        <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />
      ) : data ? (
        <div className="space-y-4">
          <ReportTable
            head={
              <>
                <Th>نوع</Th>
                <Th>تعداد</Th>
                <Th className="text-left">جمع مبلغ</Th>
                <Th>حساب نگاشت</Th>
                <Th className="text-left">اعتبار دفتر کل</Th>
                <Th>سررسید (وام)</Th>
                <Th>تطبیق</Th>
              </>
            }
          >
            {data.types.map((t) => (
              <tr key={t.funding_type}>
                <Td className="font-semibold">{TYPE_LABELS[t.funding_type] ?? t.funding_type}</Td>
                <Td className="tabular-nums">{t.count.toLocaleString("fa-IR")}</Td>
                <Td className="text-left tabular-nums"><Money value={t.total} /></Td>
                <Td><span dir="ltr" className="tabular-nums">{t.account_code}</span></Td>
                <Td className="text-left tabular-nums"><Money value={t.ledger_credit} /></Td>
                <Td className="whitespace-nowrap">
                  {t.maturity_date ? formatJalaliLong(new Date(t.maturity_date + "T12:00:00")) : "—"}
                </Td>
                <Td>
                  <span className={`text-[11px] font-bold ${t.reconciled ? "text-success-strong" : "text-danger-strong"}`}>
                    {t.reconciled ? "تطبیق" : "نامطابق"}
                  </span>
                </Td>
              </tr>
            ))}
          </ReportTable>
          <TotalRow label="جمع تأمین مالی دوره" value={data.total} />
          <p className="rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
            <b className="text-text">تطبیق:</b> جمع رویدادهای هر نوع باید برابر با اعتبار ثبتشده روی
            حساب نگاشت همان نوع (مثلاً سرمایهگذاری ← ۳۰۱ سرمایه مالک، وام ← ۲۰۵ وام دریافتی) در
            سندهای دفتر کل باشد. وام و سرمایه هرگز به عنوان درآمد ثبت نمیشوند.
          </p>
        </div>
      ) : null}
    </div>
  );
}
