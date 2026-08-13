"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { reportsApi } from "@/lib/api";
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

function Section({
  title,
  rows,
}: {
  title: string;
  rows: { code: string; name: string; amount: number }[];
}) {
  if (rows.length === 0) return null;
  return (
    <section className="card overflow-hidden">
      <div className="card-head">
        <h2 className="text-sm font-extrabold">{title}</h2>
        <span className="mr-auto text-[11px] text-muted">{rows.length} حساب</span>
      </div>
      <ReportTable
        head={
          <>
            <Th>کد</Th>
            <Th>حساب</Th>
            <Th className="text-left">مبلغ</Th>
          </>
        }
      >
        {rows.map((r) => (
          <tr key={r.code}>
            <Td><span className="font-bold tabular-nums" dir="ltr">{r.code}</span></Td>
            <Td>{r.name}</Td>
            <Td className="text-left tabular-nums"><Money value={r.amount} /></Td>
          </tr>
        ))}
      </ReportTable>
    </section>
  );
}

export default function ProfitLossPage() {
  const [range, setRange] = useState(() => ({ from: fiscalYearStart(), to: today() }));
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "profit-loss", range.from.toISOString(), range.to.toISOString()],
    queryFn: () => reportsApi.profitLoss(range.from, range.to),
  });

  return (
    <div>
      <ReportHeader
        active="/reports/profit-loss"
        title="صورت سود و زیان"
        subtitle="درآمد و هزینه دوره با تفکیک حسابها و نتیجه خالص."
      >
        <RangePicker from={range.from} to={range.to} onChange={(from, to) => setRange({ from, to })} />
      </ReportHeader>

      {isLoading ? (
        <LoadingBlock />
      ) : isError ? (
        <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />
      ) : data ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <ReconBadge ok={data.reconciled} label="از دفتر کل" />
            <span className="text-[11px] text-muted">پیشنویسها خارج از گزارشاند</span>
          </div>
          <Section title="درآمدها" rows={data.revenue} />
          <Section title="هزینهها" rows={data.expenses} />
          <div className="grid gap-3 sm:grid-cols-3">
            <TotalRow label="جمع درآمد" value={data.total_revenue} />
            <TotalRow label="جمع هزینه" value={data.total_expenses} />
            <TotalRow
              label="نتیجه خالص (سود/زیان)"
              value={data.net_income}
              hint={data.net_income >= 0 ? "سود" : "زیان"}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
