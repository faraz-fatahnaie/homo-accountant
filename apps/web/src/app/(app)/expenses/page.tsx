"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { contactsApi, expensesApi, PAYMENT_METHOD_LABELS, projectsApi, type ExpenseOut } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalaliLong, formatRials } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

function StatusBadge({ status }: { status: ExpenseOut["status"] }) {
  if (status === "posted") return <Badge tone="success">ثبت‌شده</Badge>;
  if (status === "voided") return <Badge tone="danger">برگشت خورده</Badge>;
  return <Badge tone="muted">پیش‌نویس</Badge>;
}

export default function ExpensesPage() {
  const { isWriter, canDraft } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["expenses"],
    queryFn: expensesApi.list,
  });
  const { data: contacts } = useQuery({ queryKey: ["contacts"], queryFn: () => contactsApi.list() });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: () => projectsApi.list() });

  const [filter, setFilter] = useState<"all" | "draft" | "posted" | "voided">("all");

  const contactNames = useMemo(
    () => new Map((contacts ?? []).map((c) => [c.id, c.name])),
    [contacts],
  );
  const projectNames = useMemo(
    () => new Map((projects ?? []).map((p) => [p.id, p.name])),
    [projects],
  );

  const visible = useMemo(() => {
    const list = data ?? [];
    return filter === "all" ? list : list.filter((e) => e.status === filter);
  }, [data, filter]);

  const totals = useMemo(() => {
    const posted = (data ?? []).filter((e) => e.status === "posted");
    return {
      count: (data ?? []).length,
      postedSum: posted.reduce((s, e) => s + e.amount, 0),
    };
  }, [data]);

  const postMutation = useMutation({
    mutationFn: (id: number) => expensesApi.post(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["expenses"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
  });
  const voidMutation = useMutation({
    mutationFn: (id: number) => expensesApi.voidEntry(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["expenses"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">هزینه‌ها</h1>
          <p className="mt-0.5 text-xs text-muted">
            {totals.count} هزینه · ثبت‌شده: <b className="tabular-nums">{formatRials(totals.postedSum)}</b> ریال
          </p>
        </div>
        {canDraft ? (
          <Link href="/expenses/new" className="btn btn-primary">+ هزینه جدید</Link>
        ) : null}
      </div>

      <div className="mb-3 flex gap-2">
        {(["all", "draft", "posted", "voided"] as const).map((f) => (
          <button
            key={f}
            className={`chip ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
            aria-pressed={filter === f}
          >
            {f === "all" ? "همه" : f === "draft" ? "پیش‌نویس" : f === "posted" ? "ثبت‌شده" : "برگشتی"}
          </button>
        ))}
      </div>

      {isLoading ? <LoadingBlock /> : null}
      {isError ? <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} /> : null}
      {postMutation.isError || voidMutation.isError ? (
        <div className="mb-3">
          <ErrorBlock message={(postMutation.error ?? voidMutation.error) instanceof Error ? (postMutation.error ?? voidMutation.error as Error).message : "عملیات انجام نشد."} />
        </div>
      ) : null}

      {visible.length === 0 ? (
        <div className="card px-4 py-10 text-center text-sm text-muted">
          هزینه‌ای در این وضعیت یافت نشد.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-right text-sm">
              <thead>
                <tr className="border-b-2 border-border-strong bg-surface-2 text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2.5">شماره</th>
                  <th className="px-3 py-2.5">تاریخ</th>
                  <th className="px-3 py-2.5">شرح</th>
                  <th className="px-3 py-2.5">طرف‌حساب</th>
                  <th className="px-3 py-2.5">حساب</th>
                  <th className="px-3 py-2.5">پرداخت</th>
                  <th className="px-3 py-2.5 text-left">مبلغ (ریال)</th>
                  <th className="px-3 py-2.5">وضعیت</th>
                  <th className="px-3 py-2.5 text-left">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {visible.map((e) => (
                  <tr key={e.id} className="hover:bg-[var(--row-hover)]">
                    <td className="px-3 py-2.5 font-bold" dir="ltr">
                      {e.number ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {formatJalaliLong(new Date(e.entry_date + "T12:00:00"))}
                    </td>
                    <td className="px-3 py-2.5 max-w-[220px] truncate">{e.description}</td>
                    <td className="px-3 py-2.5 text-muted">
                      {e.contact_id ? contactNames.get(e.contact_id) ?? "—" : "—"}
                      {e.project_id ? <div className="text-[10px]">{projectNames.get(e.project_id)}</div> : null}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted">
                      <span dir="ltr">{e.account_code}</span> {e.account_name}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted">{PAYMENT_METHOD_LABELS[e.payment_method]}</td>
                    <td className="px-3 py-2.5 text-left font-bold tabular-nums">{formatRials(e.amount)}</td>
                    <td className="px-3 py-2.5"><StatusBadge status={e.status} /></td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-1">
                        {e.status === "draft" && isWriter ? (
                          <button
                            className="btn btn-ghost btn-sm"
                            disabled={postMutation.isPending}
                            onClick={() => postMutation.mutate(e.id)}
                          >
                            ثبت نهایی
                          </button>
                        ) : null}
                        {e.status === "posted" && isWriter ? (
                          <button
                            className="btn btn-danger-ghost btn-sm"
                            disabled={voidMutation.isPending}
                            onClick={() => {
                              if (window.confirm("این هزینه برگشت (معکوس) می‌شود و سند برگشتی ثبت میگردد. ادامه می‌دهید؟"))
                                voidMutation.mutate(e.id);
                            }}
                          >
                            برگشت
                          </button>
                        ) : null}
                        {e.attachments.length > 0 ? (
                          <span className="inline-flex items-center gap-1 text-xs text-muted" title={`${e.attachments.length} پیوست`}>
                            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                              <path d="M21.4 11.1l-8.6 8.6a5.6 5.6 0 0 1-8-8L13 4.1a3.6 3.6 0 0 1 5.1 5.1l-8.1 8.1a1.7 1.7 0 0 1-2.4-2.4l7.7-7.7" />
                            </svg>
                            {e.attachments.length}
                          </span>
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
