"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountsApi, ApiError, entriesApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalali, parseAmount, parseJalaliInput, todayJalali } from "@/lib/format";

interface Line {
  key: number;
  accountCode: string;
  debit: string;
  credit: string;
}

let lineKey = 1;

export default function NewEntryPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isWriter, loading: authLoading } = useAuth();

  const [dateInput, setDateInput] = useState(() => {
    const [jy, jm, jd] = todayJalali();
    return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  });
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<Line[]>([
    { key: lineKey++, accountCode: "", debit: "", credit: "" },
    { key: lineKey++, accountCode: "", debit: "", credit: "" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [postAfter, setPostAfter] = useState(false);

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountsApi.list,
  });

  useEffect(() => {
    if (!authLoading && !isWriter) router.replace("/transactions");
  }, [authLoading, isWriter, router]);

  const activeAccounts = useMemo(
    () => (accounts ?? []).filter((a) => a.is_active),
    [accounts],
  );

  const totals = useMemo(() => {
    const debit = lines.reduce((s, l) => s + (parseAmount(l.debit) || 0), 0);
    const credit = lines.reduce((s, l) => s + (parseAmount(l.credit) || 0), 0);
    return { debit, credit, balanced: debit > 0 && debit === credit };
  }, [lines]);

  function updateLine(key: number, patch: Partial<Line>) {
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { key: lineKey++, accountCode: "", debit: "", credit: "" }]);
  }

  function removeLine(key: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((l) => l.key !== key) : prev));
  }

  const createMutation = useMutation({
    mutationFn: async () => {
      const date = parseJalaliInput(dateInput);
      if (!date) throw new ApiError(422, { error: { code: "invalid_date", message: "تاریخ شمسی نامعتبر است" } });
      // Build a local YYYY-MM-DD (NOT toISOString, which shifts the day in
      // timezones west of UTC).
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, "0");
      const d = String(date.getDate()).padStart(2, "0");
      const entryDate = `${y}-${m}-${d}`;
      // parseAmount returns NaN for empty input; coalesce to 0 so the JSON
      // body carries integers (NaN would serialize as null and be rejected).
      const amt = (s: string) => {
        const v = parseAmount(s);
        return Number.isNaN(v) ? 0 : v;
      };
      const parsed = lines
        .filter((l) => l.accountCode.trim() !== "")
        .map((l) => ({
          account_code: l.accountCode,
          debit: amt(l.debit),
          credit: amt(l.credit),
        }));
      const withAmount = parsed.filter((l) => l.debit > 0 || l.credit > 0);
      if (withAmount.length === 0) {
        throw new ApiError(422, {
          error: { code: "no_amount", message: "حداقل یک ردیف با حساب و مبلغ وارد کنید" },
        });
      }
      if (withAmount.some((l) => l.debit > 0 && l.credit > 0)) {
        throw new ApiError(422, {
          error: { code: "line_invalid", message: "در هر ردیف فقط یک سمت (بدهکار یا بستانکار) را پر کنید" },
        });
      }
      const body = {
        entry_date: entryDate,
        memo: memo.trim(),
        lines: withAmount,
        idempotency_key: `ui-${Date.now()}`,
      };
      const entry = await entriesApi.create(body);
      if (postAfter) {
        return entriesApi.post(entry.id);
      }
      return entry;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      router.push("/transactions");
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "خطای ناشناخته");
    },
  });

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">سند حسابداری جدید</h1>
        <p className="mt-0.5 text-xs text-muted">
          سند متوازن: جمع بدهکار باید با جمع بستانکار برابر باشد
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          createMutation.mutate();
        }}
        className="card p-5"
        noValidate
      >
        <div className="mb-4 grid gap-4 md:grid-cols-2">
          <div>
            <label className="label" htmlFor="entry-date">
              تاریخ سند (شمسی) <span className="text-danger">*</span>
            </label>
            <input
              id="entry-date"
              className="input"
              dir="ltr"
              value={dateInput}
              onChange={(e) => setDateInput(e.target.value)}
              placeholder="۱۴۰۵/۰۵/۲۲"
            />
            <p className="mt-1 text-[11px] text-muted">
              امروز: {formatJalali(new Date())} — ذخیره بهصورت استاندارد (UTC)
            </p>
          </div>
          <div>
            <label className="label" htmlFor="entry-memo">
              شرح سند <span className="text-danger">*</span>
            </label>
            <input
              id="entry-memo"
              className="input"
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="مثلاً: خرید ورق فولادی ۲ تن"
              required
            />
          </div>
        </div>

        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-extrabold">ردیفهای سند</h2>
          <button type="button" className="btn btn-ghost btn-sm" onClick={addLine}>
            + افزودن ردیف
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] font-extrabold text-muted">
                <th className="px-2 py-2 text-right">حساب</th>
                <th className="px-2 py-2 text-left">بدهکار (ریال)</th>
                <th className="px-2 py-2 text-left">بستانکار (ریال)</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-dashed divide-border">
              {lines.map((line) => (
                <tr key={line.key}>
                  <td className="px-2 py-2">
                    <select
                      className="input"
                      aria-label="حساب"
                      value={line.accountCode}
                      onChange={(e) => updateLine(line.key, { accountCode: e.target.value })}
                    >
                      <option value="">انتخاب حساب…</option>
                      {activeAccounts.map((a) => (
                        <option key={a.id} value={a.code}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className="input tabular-nums"
                      dir="ltr"
                      inputMode="numeric"
                      placeholder="۰"
                      value={line.debit}
                      onChange={(e) => updateLine(line.key, { debit: e.target.value, credit: "" })}
                      aria-label="بدهکار"
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className="input tabular-nums"
                      dir="ltr"
                      inputMode="numeric"
                      placeholder="۰"
                      value={line.credit}
                      onChange={(e) => updateLine(line.key, { credit: e.target.value, debit: "" })}
                      aria-label="بستانکار"
                    />
                  </td>
                  <td className="px-2 py-2 text-left">
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label="حذف ردیف"
                      onClick={() => removeLine(line.key)}
                    >
                      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
                        <path d="M6 6l12 12M18 6L6 18" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-4 rounded-md bg-surface-2 px-4 py-3 text-sm">
          <span>
            جمع بدهکار: <b className="tabular-nums">{totals.debit.toLocaleString("en-US")}</b>
          </span>
          <span>
            جمع بستانکار: <b className="tabular-nums">{totals.credit.toLocaleString("en-US")}</b>
          </span>
          <span className={totals.balanced ? "font-bold text-success-strong" : "font-bold text-danger-strong"}>
            {totals.balanced ? "✓ سند متوازن است" : "✗ سند نامتوازن است"}
          </span>
        </div>

        {error ? (
          <p className="error mt-3" role="alert">
            {error}
          </p>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="submit" className="btn btn-primary" disabled={createMutation.isPending || accountsLoading}>
            {createMutation.isPending ? "در حال ثبت…" : "ایجاد سند"}
          </button>
          <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={postAfter}
              onChange={(e) => setPostAfter(e.target.checked)}
              className="h-4 w-4 accent-[var(--primary)]"
            />
            بلافاصله ثبت نهایی (post)
          </label>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => router.push("/transactions")}
          >
            انصراف
          </button>
        </div>
      </form>
    </div>
  );
}
