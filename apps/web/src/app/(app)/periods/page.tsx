"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { periodsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { FA_MONTHS, faDigits, formatJalaliLong } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

export default function PeriodsPage() {
  const { isWriter, isOwner } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["periods"],
    queryFn: periodsApi.list,
  });

  const closeMutation = useMutation({
    mutationFn: (id: number) => periodsApi.close(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["periods"] }),
  });
  const reopenMutation = useMutation({
    mutationFn: (id: number) => periodsApi.reopen(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["periods"] }),
  });

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">دورههای حسابداری</h1>
        <p className="mt-0.5 text-xs text-muted">
          سال مالی ۱۴۰۵ — ثبت سند در دوره بستهشده مجاز نیست؛ بازگشایی فقط توسط مدیر
        </p>
      </div>

      {isLoading ? <LoadingBlock /> : null}
      {isError ? <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} /> : null}

      {data ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-right text-sm">
              <thead>
                <tr className="border-b-2 border-border-strong bg-surface-2 text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2.5">ماه</th>
                  <th className="px-3 py-2.5">وضعیت</th>
                  <th className="px-3 py-2.5">بستهشده در</th>
                  <th className="px-3 py-2.5">بازگشایی در</th>
                  <th className="px-3 py-2.5 text-left">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {data.map((p) => (
                  <tr key={p.id} className="hover:bg-[var(--row-hover)]">
                    <td className="px-3 py-2.5 font-bold">
                      {FA_MONTHS[p.month - 1] ?? p.month} {faDigits(p.year)}
                    </td>
                    <td className="px-3 py-2.5">
                      {p.status === "open" ? (
                        <Badge tone="success">باز</Badge>
                      ) : (
                        <Badge tone="danger">بسته</Badge>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted">
                      {p.closed_at ? formatJalaliLong(new Date(p.closed_at)) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted">
                      {p.reopened_at ? formatJalaliLong(new Date(p.reopened_at)) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-left">
                      {p.status === "open" && isWriter ? (
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={closeMutation.isPending}
                          onClick={() => {
                            if (window.confirm(`دوره ${FA_MONTHS[p.month - 1]} بسته شود؟`))
                              closeMutation.mutate(p.id);
                          }}
                        >
                          بستن دوره
                        </button>
                      ) : null}
                      {p.status === "closed" && isOwner ? (
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={reopenMutation.isPending}
                          onClick={() => reopenMutation.mutate(p.id)}
                        >
                          بازگشایی (مدیر)
                        </button>
                      ) : null}
                      {p.status === "closed" && !isOwner ? (
                        <span className="text-[11px] text-muted">فقط مدیر میتواند بازگشایی کند</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
