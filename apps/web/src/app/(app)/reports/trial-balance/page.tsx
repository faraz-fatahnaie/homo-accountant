"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { reportsApi, type TrialBalanceRow } from "@/lib/api";
import { ErrorBlock, LoadingBlock } from "@/components/ui";
import {
  AsOfPicker,
  Money,
  ReconBadge,
  ReportHeader,
  ReportTable,
  Td,
  Th,
  TotalRow,
  today,
} from "../_components";

const TYPE_LABELS: Record<string, string> = {
  asset: "دارایی",
  liability: "بدهی",
  equity: "حقوق صاحبان سهام",
  revenue: "درآمد",
  expense: "هزینه",
};

function groupByType(rows: TrialBalanceRow[]) {
  const order = ["asset", "liability", "equity", "revenue", "expense"];
  return order
    .map((t) => ({ type: t, rows: rows.filter((r) => r.type === t) }))
    .filter((g) => g.rows.length > 0);
}

export default function TrialBalancePage() {
  const [asOf, setAsOf] = useState(() => today());
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "trial-balance", asOf.toISOString()],
    queryFn: () => reportsApi.trialBalance(asOf),
  });

  return (
    <div>
      <ReportHeader
        active="/reports/trial-balance"
        title="تراز آزمایشی"
        subtitle="بدهکار و بستانکار هر حساب از سندهای ثبتشده؛ جمع دو طرف همواره برابر است."
      >
        <div className="flex flex-wrap items-center gap-2">
          {data && <ReconBadge ok={data.reconciled} label={data.reconciled ? "تراز است" : "تراز نیست"} />}
          <AsOfPicker value={asOf} onChange={setAsOf} />
        </div>
      </ReportHeader>

      {isLoading ? (
        <LoadingBlock />
      ) : isError ? (
        <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />
      ) : data ? (
        <div className="space-y-4">
          {groupByType(data.rows).map((group) => (
            <section key={group.type} className="card overflow-hidden">
              <div className="card-head">
                <h2 className="text-sm font-extrabold">{TYPE_LABELS[group.type]}</h2>
                <span className="mr-auto text-[11px] text-muted">
                  {group.rows.length} حساب
                </span>
              </div>
              <ReportTable
                head={
                  <>
                    <Th>کد</Th>
                    <Th>حساب</Th>
                    <Th className="text-left">بدهکار</Th>
                    <Th className="text-left">بستانکار</Th>
                    <Th className="text-left">مانده</Th>
                  </>
                }
              >
                {group.rows.map((r) => (
                  <tr key={r.code}>
                    <Td>
                      <span className="font-bold tabular-nums" dir="ltr">{r.code}</span>
                    </Td>
                    <Td>{r.name}</Td>
                    <Td className="text-left tabular-nums"><Money value={r.debit_total} /></Td>
                    <Td className="text-left tabular-nums"><Money value={r.credit_total} /></Td>
                    <Td className="text-left tabular-nums"><Money value={r.balance} /></Td>
                  </tr>
                ))}
              </ReportTable>
            </section>
          ))}

          <div className="grid gap-3 sm:grid-cols-2">
            <TotalRow label="جمع بدهکار" value={data.total_debit} />
            <TotalRow label="جمع بستانکار" value={data.total_credit} />
          </div>
          <p className="rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
            <b className="text-text">تطبیق:</b> جمع بدهکار و بستانکار از ردیفهای سندهای ثبتشده محاسبه
            میشود و بهخاطر تعادل اجبارشده در ثبت سندها (دوطرفه) همواره برابر است. پیشنویسها هرگز
            وارد گزارش نمیشوند.
          </p>
        </div>
      ) : null}
    </div>
  );
}
