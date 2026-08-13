"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  invoicesApi,
  INVOICE_STATUS_LABELS,
  type InvoiceOut,
  type InvoiceStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalaliLong, formatRials } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

function StatusBadge({ inv }: { inv: InvoiceOut }) {
  if (inv.status === "paid") return <Badge tone="success">{INVOICE_STATUS_LABELS.paid}</Badge>;
  if (inv.status === "void") return <Badge tone="danger">{INVOICE_STATUS_LABELS.void}</Badge>;
  if (inv.status === "draft") return <Badge tone="muted">{INVOICE_STATUS_LABELS.draft}</Badge>;
  if (inv.status === "partially_paid") return <Badge tone="warn">{INVOICE_STATUS_LABELS.partially_paid}</Badge>;
  return inv.is_overdue ? (
    <Badge tone="danger">معوق</Badge>
  ) : (
    <Badge tone="info">{INVOICE_STATUS_LABELS.issued}</Badge>
  );
}

export default function InvoicesPage() {
  const { isWriter } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["invoices"],
    queryFn: invoicesApi.list,
  });
  const [filter, setFilter] = useState<"all" | InvoiceStatus | "overdue">("all");

  const issueMutation = useMutation({
    mutationFn: (id: number) => invoicesApi.issue(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
  });
  const voidMutation = useMutation({
    mutationFn: (id: number) => invoicesApi.voidEntry(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
  });

  const visible = useMemo(() => {
    const list = data ?? [];
    if (filter === "all") return list;
    if (filter === "overdue") return list.filter((i) => i.is_overdue);
    return list.filter((i) => i.status === filter);
  }, [data, filter]);

  const totals = useMemo(() => {
    const active = (data ?? []).filter((i) => i.status !== "void" && i.status !== "draft");
    return {
      count: (data ?? []).length,
      receivable: active.reduce((s, i) => s + i.balance, 0),
    };
  }, [data]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">صورتحسابهای فروش</h1>
          <p className="mt-0.5 text-xs text-muted">
            {totals.count} صورتحساب · مانده دریافتنی:{" "}
            <b className="tabular-nums">{formatRials(totals.receivable)}</b> ریال
          </p>
        </div>
        {isWriter ? (
          <Link href="/invoices/new" className="btn btn-primary">+ صورتحساب جدید</Link>
        ) : null}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {(["all", "draft", "issued", "partially_paid", "paid", "overdue", "void"] as const).map((f) => (
          <button key={f} className={`chip ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)} aria-pressed={filter === f}>
            {f === "all" ? "همه" : f === "issued" ? "صادرشده" : f === "partially_paid" ? "جزیی پرداختشده" : f === "overdue" ? "معوق" : INVOICE_STATUS_LABELS[f as InvoiceStatus]}
          </button>
        ))}
      </div>

      {isLoading ? <LoadingBlock /> : null}
      {isError ? <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} /> : null}

      {visible.length === 0 ? (
        <div className="card px-4 py-10 text-center text-sm text-muted">
          صورتحسابی در این وضعیت یافت نشد.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-right text-sm">
              <thead>
                <tr className="border-b-2 border-border-strong bg-surface-2 text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2.5">شماره</th>
                  <th className="px-3 py-2.5">مشتری</th>
                  <th className="px-3 py-2.5">صدور</th>
                  <th className="px-3 py-2.5">سررسید</th>
                  <th className="px-3 py-2.5 text-left">مبلغ (ریال)</th>
                  <th className="px-3 py-2.5 text-left">مانده</th>
                  <th className="px-3 py-2.5">وضعیت</th>
                  <th className="px-3 py-2.5 text-left">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {visible.map((inv) => (
                  <tr key={inv.id} className="hover:bg-[var(--row-hover)]">
                    <td className="px-3 py-2.5 font-bold" dir="ltr">{inv.number ?? "—"}</td>
                    <td className="px-3 py-2.5 max-w-[160px] truncate">{inv.customer_name}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-xs text-muted">
                      {formatJalaliLong(new Date(inv.issue_date + "T12:00:00"))}
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-xs text-muted">
                      {formatJalaliLong(new Date(inv.due_date + "T12:00:00"))}
                    </td>
                    <td className="px-3 py-2.5 text-left font-bold tabular-nums">{formatRials(inv.total)}</td>
                    <td className="px-3 py-2.5 text-left tabular-nums text-muted">{formatRials(inv.balance)}</td>
                    <td className="px-3 py-2.5"><StatusBadge inv={inv} /></td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link href={`/invoices/${inv.id}`} className="btn btn-ghost btn-sm">مشاهده</Link>
                        {inv.status === "draft" && isWriter ? (
                          <button className="btn btn-ghost btn-sm" disabled={issueMutation.isPending}
                            onClick={() => issueMutation.mutate(inv.id)}>
                            صدور
                          </button>
                        ) : null}
                        {inv.status !== "draft" && inv.status !== "void" ? (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                              void invoicesApi
                                .downloadPdf(inv.id, `invoice-${inv.number ?? inv.id}.pdf`)
                                .catch(() => undefined);
                            }}
                          >
                            PDF
                          </button>
                        ) : null}
                        {(inv.status === "issued" || inv.status === "partially_paid") && isWriter ? (
                          <button className="btn btn-danger-ghost btn-sm" disabled={voidMutation.isPending}
                            onClick={() => {
                              if (window.confirm("صورتحساب باطل شود؟ (فقط اگر پرداختی نداشته باشد)"))
                                voidMutation.mutate(inv.id);
                            }}>
                            باطل
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
      )}
    </div>
  );
}
