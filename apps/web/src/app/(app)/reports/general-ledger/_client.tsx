"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { accountsApi, reportsApi } from "@/lib/api";
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

export function GeneralLedgerClient({ initialAccountCode }: { initialAccountCode: string }) {
  const [code, setCode] = useState(initialAccountCode);
  const [range, setRange] = useState(() => ({ from: fiscalYearStart(), to: today() }));

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => accountsApi.list(),
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "general-ledger", code, range.from.toISOString(), range.to.toISOString()],
    queryFn: () => reportsApi.generalLedger(code, range.from, range.to),
    enabled: code.length > 0,
  });

  return (
    <div>
      <ReportHeader
        active="/reports/general-ledger"
        title="دفتر کل"
        subtitle="گردش یک حساب با مانده تجمعی؛ با کلیک روی حساب در ترازنامه یا تراز آزمایشی باز می‌شود."
      >
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-bold text-muted" htmlFor="gl-account">
            حساب
          </label>
          <select
            id="gl-account"
            className="input w-auto"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          >
            <option value="">انتخاب حساب…</option>
            {(accounts ?? []).map((a) => (
              <option key={a.code} value={a.code}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
          <RangePicker from={range.from} to={range.to} onChange={(from, to) => setRange({ from, to })} />
        </div>
      </ReportHeader>

      {!code ? (
        <div className="card p-6 text-sm text-muted">برای مشاهده دفتر کل یک حساب انتخاب کنید.</div>
      ) : isLoading ? (
        <LoadingBlock />
      ) : isError ? (
        <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />
      ) : data ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-sm font-extrabold">
              {data.account.name} <span dir="ltr" className="tabular-nums">({data.account.code})</span>
            </h2>
            <ReconBadge ok={data.reconciled} label="از دفتر کل" />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <TotalRow label="مانده اول دوره" value={data.opening_balance} />
            <TotalRow label="مانده آخر دوره" value={data.closing_balance} />
            <TotalRow label="تعداد ردیف" value={data.lines.length} hint="سند" />
          </div>
          <ReportTable
            head={
              <>
                <Th>تاریخ</Th>
                <Th>شماره</Th>
                <Th>شرح</Th>
                <Th className="text-left">بدهکار</Th>
                <Th className="text-left">بستانکار</Th>
                <Th className="text-left">مانده</Th>
              </>
            }
          >
            {data.lines.map((l) => (
              <tr key={l.entry_id}>
                <Td className="whitespace-nowrap">{formatJalaliLong(new Date(l.date + "T12:00:00"))}</Td>
                <Td><span className="tabular-nums" dir="ltr">{l.reference ?? "—"}</span></Td>
                <Td className="max-w-xs truncate">{l.memo}</Td>
                <Td className="text-left tabular-nums">{l.debit > 0 ? <Money value={l.debit} /> : "—"}</Td>
                <Td className="text-left tabular-nums">{l.credit > 0 ? <Money value={l.credit} /> : "—"}</Td>
                <Td className="text-left tabular-nums"><Money value={l.balance} /></Td>
              </tr>
            ))}
          </ReportTable>
        </div>
      ) : null}
    </div>
  );
}
