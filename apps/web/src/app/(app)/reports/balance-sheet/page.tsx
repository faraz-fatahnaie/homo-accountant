"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { reportsApi } from "@/lib/api";
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

function SheetSection({
  title,
  rows,
  linkAccount,
}: {
  title: string;
  rows: { code: string; name: string; amount: number }[];
  linkAccount?: (code: string) => string | undefined;
}) {
  if (rows.length === 0) return null;
  return (
    <section className="card overflow-hidden">
      <div className="card-head">
        <h2 className="text-sm font-extrabold">{title}</h2>
        <span className="mr-auto text-[11px] text-muted">{rows.length} قلم</span>
      </div>
      <ReportTable
        head={
          <>
            <Th>کد</Th>
            <Th>عنوان</Th>
            <Th className="text-left">مبلغ</Th>
          </>
        }
      >
        {rows.map((r) => {
          const href = linkAccount?.(r.code);
          return (
            <tr key={r.code}>
              <Td>
                <span className="font-bold tabular-nums" dir="ltr">{r.code}</span>
              </Td>
              <Td>
                {href ? (
                  <Link href={href} className="font-semibold underline-offset-2 hover:underline">
                    {r.name}
                  </Link>
                ) : (
                  r.name
                )}
              </Td>
              <Td className="text-left tabular-nums"><Money value={r.amount} /></Td>
            </tr>
          );
        })}
      </ReportTable>
    </section>
  );
}

export default function BalanceSheetPage() {
  const [asOf, setAsOf] = useState(() => today());
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "balance-sheet", asOf.toISOString()],
    queryFn: () => reportsApi.balanceSheet(asOf),
  });

  return (
    <div>
      <ReportHeader
        active="/reports/balance-sheet"
        title="ترازنامه"
        subtitle="دارایی‌ها در برابر بدهی‌ها و حقوق صاحبان سهام (شامل سود/زیان دوره)."
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
          <SheetSection title="دارایی‌ها" rows={data.assets} linkAccount={(c) => `/reports/general-ledger?account_code=${c}`} />
          <SheetSection title="بدهی‌ها" rows={data.liabilities} linkAccount={(c) => `/reports/general-ledger?account_code=${c}`} />
          <SheetSection title="حقوق صاحبان سهام" rows={data.equity} linkAccount={(c) => (c === "PNL" ? undefined : `/reports/general-ledger?account_code=${c}`)} />

          <div className="grid gap-3 sm:grid-cols-2">
            <TotalRow label="جمع دارایی‌ها" value={data.total_assets} />
            <TotalRow label="جمع بدهی‌ها و حقوق صاحبان سهام" value={data.total_liabilities_equity} />
          </div>
          <p className="rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
            <b className="text-text">تطبیق:</b> «سود (زیان) دوره» از درآمدها منهای هزینه‌های ثبت‌شده
            تا تاریخ گزارش محاسبه و به حقوق صاحبان سهام اضافه می‌شود. معادله «دارایی = بدهی + سرمایه»
            با این قلم همواره برقرار است.
          </p>
        </div>
      ) : null}
    </div>
  );
}
