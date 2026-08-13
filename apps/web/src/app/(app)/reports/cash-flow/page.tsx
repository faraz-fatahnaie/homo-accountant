"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { reportsApi, type CashFlowSection } from "@/lib/api";
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

const SECTION_LABELS: Record<string, { label: string; desc: string }> = {
  operating: { label: "فعالیتهای عملیاتی", desc: "درآمد/هزینه نقدی و تغییر در دریافتنی و پرداختنی" },
  financing: { label: "فعالیتهای تأمین مالی", desc: "سرمایه مالک و وامها" },
  investing: { label: "فعالیتهای سرمایهگذاری", desc: "خرید/فروش داراییهای ثابت" },
  other: { label: "سایر", desc: "مواردی که در بخشهای بالا جای نگرفتند" },
};

function Section({ key, data }: { key: string; data: CashFlowSection }) {
  const meta = SECTION_LABELS[key] ?? { label: "سایر", desc: "موارد متفرقه" };
  return (
    <section className="card overflow-hidden">
      <div className="card-head">
        <h2 className="text-sm font-extrabold">{meta.label}</h2>
        <span className="mr-auto text-[11px] text-muted">{meta.desc}</span>
      </div>
      <ReportTable
        head={
          <>
            <Th>تاریخ</Th>
            <Th>شماره / شرح</Th>
            <Th>حساب مقابل</Th>
            <Th className="text-left">ورود</Th>
            <Th className="text-left">خروج</Th>
            <Th className="text-left">خالص</Th>
          </>
        }
      >
        {data.items.length === 0 ? (
          <tr>
            <Td className="py-4 text-muted" >
              <span className="px-3">حرکتی در این بخش نبود.</span>
            </Td>
          </tr>
        ) : (
          data.items.map((i) => (
            <tr key={i.entry_id}>
              <Td className="whitespace-nowrap">{formatJalaliLong(new Date(i.date + "T12:00:00"))}</Td>
              <Td>
                <div className="truncate font-semibold">{i.memo}</div>
                <div className="text-[10px] text-muted" dir="ltr">{i.reference ?? "—"}</div>
              </Td>
              <Td>
                {i.counterparts.map((c) => (
                  <span key={c.code} className="me-1 inline-block rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted" dir="ltr">
                    {c.code}
                  </span>
                ))}
              </Td>
              <Td className="text-left tabular-nums">{i.inflow > 0 ? <Money value={i.inflow} /> : "—"}</Td>
              <Td className="text-left tabular-nums">{i.outflow > 0 ? <Money value={i.outflow} /> : "—"}</Td>
              <Td className="text-left tabular-nums"><Money value={i.net} /></Td>
            </tr>
          ))
        )}
      </ReportTable>
      <div className="flex flex-wrap gap-2 border-t border-border px-3 py-2 text-xs">
        <span className="font-bold">ورود: <b className="tabular-nums">{data.inflow.toLocaleString("fa-IR")}</b></span>
        <span className="font-bold">خروج: <b className="tabular-nums">{data.outflow.toLocaleString("fa-IR")}</b></span>
        <span className="font-bold">خالص: <Money value={data.net} /></span>
      </div>
    </section>
  );
}

export default function CashFlowPage() {
  const [range, setRange] = useState(() => ({ from: fiscalYearStart(), to: today() }));
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "cash-flow", range.from.toISOString(), range.to.toISOString()],
    queryFn: () => reportsApi.cashFlow(range.from, range.to),
  });

  return (
    <div>
      <ReportHeader
        active="/reports/cash-flow"
        title="صورت جریان وجوه نقد"
        subtitle="روش مستقیم روی حسابهای نقد (۱۰۱) و بانک (۱۰۲) از دفتر کل."
      >
        <div className="flex flex-wrap items-center gap-2">
          {data && <ReconBadge ok={data.reconciled} label={data.reconciled ? "تطبیق شد" : "تطبیق نشد"} />}
          <RangePicker from={range.from} to={range.to} onChange={(from, to) => setRange({ from, to })} />
        </div>
      </ReportHeader>

      {isLoading ? (
        <LoadingBlock />
      ) : isError ? (
        <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} />
      ) : data ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <TotalRow label="موجودی نقد و بانک (ابتدا)" value={data.beginning_cash_bank} />
            <TotalRow label="تغییر خالص دوره" value={data.net_change} />
            <TotalRow label="موجودی نقد و بانک (انتها)" value={data.ending_cash_bank} />
          </div>
          <Section key="operating" data={data.sections.operating} />
          <Section key="financing" data={data.sections.financing} />
          <Section key="investing" data={data.sections.investing} />
          <Section key="other" data={data.sections.other} />
          <p className="rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
            <b className="text-text">روش و تطبیق:</b> این گزارش به روش مستقیم از ردیفهای سندهای
            ثبتشده روی حسابهای صندوق (۱۰۱) و بانک (۱۰۲) ساخته میشود و هر حرکت بر اساس حساب مقابل
            طبقهبندی میشود (عملیاتی ← تأمین مالی ← سرمایهگذاری). معادله «موجودی ابتدا + تغییرات =
            موجودی انتها» مستقیماً از دفتر کل بررسی میشود.
          </p>
        </div>
      ) : null}
    </div>
  );
}
