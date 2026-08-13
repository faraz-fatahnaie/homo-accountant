"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BILL_STATUS_LABELS, billsApi, type BillOut, type BillStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalaliLong, formatRials } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

function StatusBadge({ bill }: { bill: BillOut }) {
  if (bill.status === "paid") return <Badge tone="success">{BILL_STATUS_LABELS.paid}</Badge>;
  if (bill.status === "void") return <Badge tone="danger">{BILL_STATUS_LABELS.void}</Badge>;
  if (bill.status === "draft") return <Badge tone="muted">{BILL_STATUS_LABELS.draft}</Badge>;
  if (bill.status === "partially_paid") return <Badge tone="warn">{BILL_STATUS_LABELS.partially_paid}</Badge>;
  return bill.is_overdue ? (
    <Badge tone="danger">معوق</Badge>
  ) : (
    <Badge tone="info">{BILL_STATUS_LABELS.open}</Badge>
  );
}

export default function BillsPage() {
  const { isWriter } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["bills"],
    queryFn: billsApi.list,
  });
  const [filter, setFilter] = useState<"all" | BillStatus | "overdue">("all");

  const postMutation = useMutation({
    mutationFn: (id: number) => billsApi.post(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["bills"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
  });
  const voidMutation = useMutation({
    mutationFn: (id: number) => billsApi.voidEntry(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["bills"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
  });

  const visible = useMemo(() => {
    const list = data ?? [];
    if (filter === "all") return list;
    if (filter === "overdue") return list.filter((b) => b.is_overdue);
    return list.filter((b) => b.status === filter);
  }, [data, filter]);

  const totals = useMemo(() => {
    const active = (data ?? []).filter((b) => b.status !== "void" && b.status !== "draft");
    return {
      count: (data ?? []).length,
      payable: active.reduce((s, b) => s + b.balance, 0),
    };
  }, [data]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">فاکتورهای خرید (پرداختنیها)</h1>
          <p className="mt-0.5 text-xs text-muted">
            {totals.count} فاکتور · مانده پرداختنی:{" "}
            <b className="tabular-nums">{formatRials(totals.payable)}</b> ریال
          </p>
        </div>
        {isWriter ? (
          <Link href="/bills/new" className="btn btn-primary">+ فاکتور خرید جدید</Link>
        ) : null}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {(["all", "draft", "open", "partially_paid", "paid", "overdue", "void"] as const).map((f) => (
          <button key={f} className={`chip ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)} aria-pressed={filter === f}>
            {f === "all" ? "همه" : f === "open" ? "باز" : f === "partially_paid" ? "جزیی پرداختشده" : f === "overdue" ? "معوق" : BILL_STATUS_LABELS[f as BillStatus]}
          </button>
        ))}
      </div>

      {isLoading ? <LoadingBlock /> : null}
      {isError ? <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} /> : null}

      {visible.length === 0 ? (
        <div className="card px-4 py-10 text-center text-sm text-muted">
          فاکتور خریدی در این وضعیت یافت نشد.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-right text-sm">
              <thead>
                <tr className="border-b-2 border-border-strong bg-surface-2 text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2.5">شماره</th>
                  <th className="px-3 py-2.5">تأمینکننده</th>
                  <th className="px-3 py-2.5">شرح</th>
                  <th className="px-3 py-2.5">سررسید</th>
                  <th className="px-3 py-2.5 text-left">مبلغ (ریال)</th>
                  <th className="px-3 py-2.5 text-left">مانده</th>
                  <th className="px-3 py-2.5">وضعیت</th>
                  <th className="px-3 py-2.5 text-left">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {visible.map((bill) => (
                  <tr key={bill.id} className="hover:bg-[var(--row-hover)]">
                    <td className="px-3 py-2.5 font-bold" dir="ltr">{bill.number ?? "—"}</td>
                    <td className="px-3 py-2.5 max-w-[160px] truncate">{bill.vendor_name}</td>
                    <td className="px-3 py-2.5 max-w-[180px] truncate">{bill.memo}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-xs text-muted">
                      {formatJalaliLong(new Date(bill.due_date + "T12:00:00"))}
                    </td>
                    <td className="px-3 py-2.5 text-left font-bold tabular-nums">{formatRials(bill.total)}</td>
                    <td className="px-3 py-2.5 text-left tabular-nums text-muted">{formatRials(bill.balance)}</td>
                    <td className="px-3 py-2.5"><StatusBadge bill={bill} /></td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link href={`/bills/${bill.id}`} className="btn btn-ghost btn-sm">مشاهده</Link>
                        {bill.status === "draft" && isWriter ? (
                          <button className="btn btn-ghost btn-sm" disabled={postMutation.isPending}
                            onClick={() => postMutation.mutate(bill.id)}>
                            ثبت نهایی
                          </button>
                        ) : null}
                        {(bill.status === "open" || bill.status === "partially_paid") && isWriter ? (
                          <button className="btn btn-danger-ghost btn-sm" disabled={voidMutation.isPending}
                            onClick={() => {
                              if (window.confirm("فاکتور خرید باطل شود؟ (فقط بدون پرداخت)"))
                                voidMutation.mutate(bill.id);
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
