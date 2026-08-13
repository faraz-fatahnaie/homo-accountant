"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { reportsApi, type BudgetRow } from "@/lib/api";
import { ErrorBlock, LoadingBlock } from "@/components/ui";
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

const STATUS_LABELS: Record<string, string> = {
  active: "فعال",
  completed: "تکمیلشده",
  on_hold: "معلق",
};

function Utilization({ value, amount }: { value: number | null; amount: number }) {
  if (value === null || amount === 0) return <span className="text-muted">—</span>;
  const pct = Math.round(value * 100);
  const tone = pct > 100 ? "text-danger-strong" : pct >= 80 ? "text-warning-strong" : "text-success-strong";
  return <span className={`font-bold ${tone}`}>{pct.toLocaleString("fa-IR")}٪</span>;
}

export default function BudgetPage() {
  const [range, setRange] = useState(() => ({ from: fiscalYearStart(), to: today() }));
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "budget-vs-actual", range.from.toISOString(), range.to.toISOString()],
    queryFn: () => reportsApi.budgetVsActual(range.from, range.to),
  });

  return (
    <div>
      <ReportHeader
        active="/reports/budget"
        title="بودجه و عملکرد پروژهها"
        subtitle="مقایسه بودجه هر پروژه با هزینههای ثبتشده (پستشده) در بازه انتخابی."
      >
        <div className="flex flex-wrap items-center gap-2">
          {data && <ReconBadge ok={data.reconciled} label="از هزینههای ثبتشده" />}
          <RangePicker from={range.from} to={range.to} onChange={(from, to) => setRange({ from, to })} />
        </div>
      </ReportHeader>

      {isLoading ? (
        <LoadingBlock />
      ) : isError ? (
        <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />
      ) : data ? (
        <div className="space-y-4">
          {data.rows.length === 0 ? (
            <div className="card p-6 text-sm text-muted">هنوز پروژهای تعریف نشده است.</div>
          ) : (
            <ReportTable
              head={
                <>
                  <Th>پروژه</Th>
                  <Th>وضعیت</Th>
                  <Th className="text-left">بودجه</Th>
                  <Th className="text-left">عملکرد (هزینه)</Th>
                  <Th className="text-left">مانده</Th>
                  <Th className="text-left">درصد مصرف</Th>
                </>
              }
            >
              {data.rows.map((r: BudgetRow) => (
                <tr key={r.project_id}>
                  <Td className="font-semibold">{r.name}</Td>
                  <Td><span className="text-[11px] text-muted">{STATUS_LABELS[r.status] ?? r.status}</span></Td>
                  <Td className="text-left tabular-nums"><Money value={r.budget} /></Td>
                  <Td className="text-left tabular-nums"><Money value={r.actual} /></Td>
                  <Td className="text-left tabular-nums"><Money value={r.remaining} /></Td>
                  <Td className="text-left"><Utilization value={r.utilization} amount={r.budget} /></Td>
                </tr>
              ))}
            </ReportTable>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <TotalRow label="جمع بودجه" value={data.total_budget} />
            <TotalRow label="جمع عملکرد" value={data.total_actual} />
            <TotalRow label="مانده کل" value={data.total_remaining} />
          </div>
          <p className="rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
            <b className="text-text">تطبیق:</b> «عملکرد» مجموع هزینههای ثبتشده (پستشده و غیر باطل)
            تخصیصیافته به هر پروژه است؛ پشت هر هزینه سند دفتر کل (حساب هزینه) وجود دارد. هزینههای
            بدون تخصیص پروژه در این گزارش دیده نمیشوند.
          </p>
        </div>
      ) : null}
    </div>
  );
}
