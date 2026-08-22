"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { reportsApi, type AgingRow } from "@/lib/api";
import { ErrorBlock, LoadingBlock } from "@/components/ui";
import { formatJalaliLong } from "@/lib/format";
import {
  AsOfPicker,
  Money,
  ReconBadge,
  ReportHeader,
  ReportTable,
  Td,
  Th,
  today,
} from "../_components";

const BUCKET_ORDER = ["current", "1_30", "31_60", "61_90", "over_90"];

function Side({
  title,
  side,
}: {
  title: string;
  side: { rows: AgingRow[]; buckets: { key: string; label: string; amount: number }[]; total: number; ledger_balance: number; reconciled: boolean };
}) {
  return (
    <section className="card overflow-hidden">
      <div className="card-head">
        <h2 className="text-sm font-extrabold">{title}</h2>
        <span className="mr-auto">
          <ReconBadge ok={side.reconciled} label={side.reconciled ? "تطبیق با دفتر کل" : "عدم تطبیق"} />
        </span>
      </div>
      <div className="flex flex-wrap gap-2 border-b border-border px-3 py-2">
        {BUCKET_ORDER.map((key) => {
          const b = side.buckets.find((x) => x.key === key);
          if (!b) return null;
          return (
            <span key={key} className={`rounded-md px-2 py-1 text-[11px] font-bold ${b.amount > 0 && key !== "current" ? "bg-danger-soft text-danger-strong" : "bg-surface-2 text-muted"}`}>
              {b.label}: <b className="tabular-nums">{b.amount.toLocaleString("fa-IR")}</b>
            </span>
          );
        })}
      </div>
      {side.rows.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted">موردی نیست.</div>
      ) : (
        <ReportTable
          head={
            <>
              <Th>شماره</Th>
              <Th>طرف‌حساب</Th>
              <Th>سررسید</Th>
              <Th className="text-left">کل</Th>
              <Th className="text-left">پرداخت‌شده</Th>
              <Th className="text-left">مانده</Th>
              <Th>گروه سنی</Th>
            </>
          }
        >
          {side.rows.map((r, i) => (
            <tr key={`${r.number}-${i}`}>
              <Td><span className="tabular-nums" dir="ltr">{r.number ?? "—"}</span></Td>
              <Td>{r.contact_name}</Td>
              <Td className="whitespace-nowrap">{formatJalaliLong(new Date(r.due_date + "T12:00:00"))}</Td>
              <Td className="text-left tabular-nums"><Money value={r.total} /></Td>
              <Td className="text-left tabular-nums"><Money value={r.paid} /></Td>
              <Td className="text-left tabular-nums"><Money value={r.balance} /></Td>
              <Td>{side.buckets.find((b) => b.key === r.bucket)?.label ?? r.bucket}</Td>
            </tr>
          ))}
        </ReportTable>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-3 py-2 text-xs">
        <span className="font-bold">
          جمع گروهها: <b className="tabular-nums">{side.total.toLocaleString("fa-IR")}</b> ریال
        </span>
        <span className="text-muted">
          مانده دفتر کل (حساب{" "}
          <b dir="ltr" className="tabular-nums">{title.startsWith("دریافت") ? "۲۰۳" : "۲۰۴"}</b>):{" "}
          <b className="tabular-nums">{side.ledger_balance.toLocaleString("fa-IR")}</b> ریال
        </span>
      </div>
    </section>
  );
}

export default function AgingPage() {
  const [asOf, setAsOf] = useState(() => today());
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "aging", asOf.toISOString()],
    queryFn: () => reportsApi.aging(asOf),
  });

  return (
    <div>
      <ReportHeader
        active="/reports/aging"
        title="سررسید دریافتنی و پرداختنی"
        subtitle="سن مطالبات و بدهی‌ها به دستههای جاری، ۳۰، ۶۰، ۹۰ و بیش از ۹۰ روز."
      >
        <div className="flex flex-wrap items-center gap-2">
          {data && <ReconBadge ok={data.reconciled} label={data.reconciled ? "تطبیق شد" : "تطبیق نشد"} />}
          <AsOfPicker value={asOf} onChange={setAsOf} />
        </div>
      </ReportHeader>

      {isLoading ? (
        <LoadingBlock />
      ) : isError ? (
        <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />
      ) : data ? (
        <div className="space-y-4">
          <Side title="دریافتنی (حساب ۲۰۳)" side={data.receivable} />
          <Side title="پرداختنی (حساب ۲۰۴)" side={data.payable} />
        </div>
      ) : null}
    </div>
  );
}
