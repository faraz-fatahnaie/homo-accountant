"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountsApi, ApiError, type AccountOut, type AccountType } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

const TYPE_LABELS: Record<AccountType, string> = {
  asset: "دارایی",
  liability: "بدهی",
  equity: "سرمایه (حقوق صاحبان سهام)",
  revenue: "درآمد",
  expense: "هزینه",
};

const TYPE_ORDER: AccountType[] = ["asset", "liability", "equity", "revenue", "expense"];

export default function AccountsPage() {
  const { isWriter } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountsApi.list,
  });

  const [showForm, setShowForm] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("asset");
  const [formError, setFormError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (body: { code: string; name: string; type: AccountType }) =>
      accountsApi.create(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setShowForm(false);
      setCode("");
      setName("");
      setType("asset");
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "خطای ناشناخته");
    },
  });

  const grouped = useMemo(() => {
    const map = new Map<AccountType, AccountOut[]>();
    for (const t of TYPE_ORDER) map.set(t, []);
    for (const a of data ?? []) map.get(a.type)?.push(a);
    return map;
  }, [data]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">حسابها (کدینگ)</h1>
          <p className="mt-0.5 text-xs text-muted">نمودار حسابها — {(data ?? []).length} حساب</p>
        </div>
        {isWriter ? (
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "بستن فرم" : "+ حساب جدید"}
          </button>
        ) : null}
      </div>

      {showForm && isWriter ? (
        <form
          className="card mb-4 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            setFormError(null);
            createMutation.mutate({ code: code.trim(), name: name.trim(), type });
          }}
        >
          <div className="grid gap-3 md:grid-cols-4">
            <div>
              <label className="label" htmlFor="acc-code">کد</label>
              <input id="acc-code" className="input" dir="ltr" value={code}
                onChange={(e) => setCode(e.target.value)} placeholder="۱۰۳" required />
            </div>
            <div>
              <label className="label" htmlFor="acc-name">نام</label>
              <input id="acc-name" className="input" value={name}
                onChange={(e) => setName(e.target.value)} placeholder="بانک سپرده" required />
            </div>
            <div>
              <label className="label" htmlFor="acc-type">نوع</label>
              <select id="acc-type" className="input" value={type}
                onChange={(e) => setType(e.target.value as AccountType)}>
                {TYPE_ORDER.map((t) => (
                  <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                ))}
              </select>
            </div>
            <div className="flex items-end gap-2">
              <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                ایجاد
              </button>
            </div>
          </div>
          {formError ? <p className="error mt-2" role="alert">{formError}</p> : null}
        </form>
      ) : null}

      {isLoading ? <LoadingBlock /> : null}
      {isError ? <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} /> : null}

      {data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {TYPE_ORDER.map((t) => {
            const accounts = grouped.get(t) ?? [];
            if (accounts.length === 0) return null;
            return (
              <section key={t} className="card">
                <div className="card-head">
                  <h2 className="text-sm font-extrabold">{TYPE_LABELS[t]}</h2>
                  <span className="text-xs text-muted">({accounts.length})</span>
                </div>
                <ul className="divide-y divide-dashed divide-border">
                  {accounts.map((a) => (
                    <li key={a.id} className="flex items-center gap-2 px-4 py-2 text-sm">
                      <span className="font-bold tabular-nums" dir="ltr">{a.code}</span>
                      <span className="flex-1">{a.name}</span>
                      {!a.is_active ? <Badge tone="danger">غیرفعال</Badge> : null}
                      {a.is_system ? <Badge tone="muted">سیستمی</Badge> : null}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
