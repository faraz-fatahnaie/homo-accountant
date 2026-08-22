"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, contactsApi, invoicesApi, projectsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalali, parseJalaliInput, todayJalali } from "@/lib/format";

interface Line {
  key: number;
  description: string;
  quantity: string;
  unitPrice: string;
  discount: string;
}

let lineKey = 1;

export default function NewInvoicePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isWriter, loading: authLoading } = useAuth();

  const [customerId, setCustomerId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [issueDate, setIssueDate] = useState(() => {
    const [jy, jm, jd] = todayJalali();
    return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  });
  const [dueDate, setDueDate] = useState("");
  const [lines, setLines] = useState<Line[]>([
    { key: lineKey++, description: "", quantity: "1", unitPrice: "", discount: "" },
  ]);
  const [notes, setNotes] = useState("");
  const [paymentInstructions, setPaymentInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: customers } = useQuery({ queryKey: ["contacts"], queryFn: () => contactsApi.list(true) });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: () => projectsApi.list(true) });

  useEffect(() => {
    if (!authLoading && !isWriter) router.replace("/invoices");
  }, [authLoading, isWriter, router]);

  const customerList = useMemo(
    () => (customers ?? []).filter((c) => c.roles.includes("customer") || c.roles.includes("other")),
    [customers],
  );

  function updateLine(key: number, patch: Partial<Line>) {
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }
  function addLine() {
    setLines((prev) => [...prev, { key: lineKey++, description: "", quantity: "1", unitPrice: "", discount: "" }]);
  }
  function removeLine(key: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((l) => l.key !== key) : prev));
  }

  const totals = useMemo(() => {
    let total = 0;
    for (const l of lines) {
      const qty = Number(l.quantity.replace(/[^\d]/g, "")) || 0;
      const price = Number(l.unitPrice.replace(/[^\d]/g, "")) || 0;
      const disc = Number(l.discount.replace(/[^\d]/g, "")) || 0;
      total += qty * price - disc;
    }
    return Math.max(total, 0);
  }, [lines]);

  const createMutation = useMutation({
    mutationFn: async () => {
      const issue = parseJalaliInput(issueDate);
      if (!issue) throw new ApiError(422, { error: { code: "invalid_date", message: "تاریخ صدور نامعتبر است" } });
      let due = dueDate ? parseJalaliInput(dueDate) : null;
      if (!due) {
        due = new Date(issue.getTime() + 30 * 24 * 3600 * 1000);
      }
      if (!customerId) throw new ApiError(422, { error: { code: "no_customer", message: "مشتری را انتخاب کنید" } });
      const items = lines
        .filter((l) => l.description.trim() !== "" && (Number(l.unitPrice) > 0))
        .map((l) => ({
          description: l.description.trim(),
          quantity: Number(l.quantity) || 1,
          unit_price: Number(l.unitPrice.replace(/[^\d]/g, "")) || 0,
          discount: Number(l.discount.replace(/[^\d]/g, "")) || 0,
        }));
      if (items.length === 0) {
        throw new ApiError(422, { error: { code: "no_items", message: "حداقل یک ردیف با شرح و قیمت وارد کنید" } });
      }
      const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      return invoicesApi.create({
        customer_id: Number(customerId),
        project_id: projectId ? Number(projectId) : null,
        issue_date: fmt(issue),
        due_date: fmt(due),
        items,
        notes: notes.trim() || null,
        payment_instructions: paymentInstructions.trim() || null,
      });
    },
    onSuccess: (invoice) => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      router.push(`/invoices/${invoice.id}`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "خطای ناشناخته"),
  });

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">صورت‌حساب جدید</h1>
        <p className="mt-0.5 text-xs text-muted">
          ابتدا پیش‌نویس ساخته می‌شود؛ سپس با دکمه «صدور» در صفحه صورت‌حساب، سند دریافتنی ثبت می‌شود
        </p>
      </div>

      <form
        className="card p-5"
        onSubmit={(e) => { e.preventDefault(); setError(null); createMutation.mutate(); }}
      >
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <label className="label" htmlFor="inv-customer">مشتری <span className="text-danger">*</span></label>
            <select id="inv-customer" className="input" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">انتخاب مشتری…</option>
              {customerList.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="inv-project">پروژه</label>
            <select id="inv-project" className="input" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">بدون پروژه</option>
              {(projects ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="inv-instructions">دستور پرداخت</label>
            <input id="inv-instructions" className="input" value={paymentInstructions}
              onChange={(e) => setPaymentInstructions(e.target.value)} placeholder="انتقال به شماره حساب…" />
          </div>
          <div>
            <label className="label" htmlFor="inv-issue">تاریخ صدور (شمسی) <span className="text-danger">*</span></label>
            <input id="inv-issue" className="input" dir="ltr" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
            <p className="mt-1 text-[11px] text-muted">امروز: {formatJalali(new Date())}</p>
          </div>
          <div>
            <label className="label" htmlFor="inv-due">سررسید (شمسی)</label>
            <input id="inv-due" className="input" dir="ltr" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
              placeholder="خالی = ۳۰ روز بعد" />
          </div>
        </div>

        <div className="mt-5 mb-2 flex items-center justify-between">
          <h2 className="text-sm font-extrabold">ردیف‌های صورت‌حساب</h2>
          <button type="button" className="btn btn-ghost btn-sm" onClick={addLine}>+ افزودن ردیف</button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] font-extrabold text-muted">
                <th className="px-2 py-2 text-right">شرح</th>
                <th className="px-2 py-2 text-left">تعداد</th>
                <th className="px-2 py-2 text-left">قیمت واحد (ریال)</th>
                <th className="px-2 py-2 text-left">تخفیف</th>
                <th className="px-2 py-2 text-left">مبلغ ردیف</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-dashed divide-border">
              {lines.map((l) => {
                const qty = Number(l.quantity) || 0;
                const price = Number(l.unitPrice.replace(/[^\d]/g, "")) || 0;
                const disc = Number(l.discount.replace(/[^\d]/g, "")) || 0;
                const lineTotal = Math.max(qty * price - disc, 0);
                return (
                  <tr key={l.key}>
                    <td className="px-2 py-2">
                      <input className="input" value={l.description} onChange={(e) => updateLine(l.key, { description: e.target.value })}
                        placeholder="شرح کالا / خدمت" />
                    </td>
                    <td className="px-2 py-2 w-20">
                      <input className="input tabular-nums" dir="ltr" inputMode="numeric" value={l.quantity}
                        onChange={(e) => updateLine(l.key, { quantity: e.target.value })} />
                    </td>
                    <td className="px-2 py-2 w-32">
                      <input className="input tabular-nums" dir="ltr" inputMode="numeric" value={l.unitPrice}
                        onChange={(e) => updateLine(l.key, { unitPrice: e.target.value })} placeholder="۲٬۵۰۰٬۰۰۰" />
                    </td>
                    <td className="px-2 py-2 w-28">
                      <input className="input tabular-nums" dir="ltr" inputMode="numeric" value={l.discount}
                        onChange={(e) => updateLine(l.key, { discount: e.target.value })} />
                    </td>
                    <td className="px-2 py-2 text-left font-bold tabular-nums">{lineTotal.toLocaleString("en-US")}</td>
                    <td className="px-2 py-2 text-left">
                      <button type="button" className="icon-btn" aria-label="حذف ردیف" onClick={() => removeLine(l.key)}>
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex justify-end text-sm">
          <span>جمع کل: <b className="tabular-nums">{totals.toLocaleString("en-US")}</b> ریال</span>
        </div>

        <div className="mt-3">
          <label className="label" htmlFor="inv-notes">یادداشت</label>
          <textarea id="inv-notes" className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        {error ? <p className="error mt-3" role="alert">{error}</p> : null}

        <div className="mt-5 flex items-center gap-3">
          <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? "در حال ساخت…" : "ایجاد صورت‌حساب"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => router.push("/invoices")}>انصراف</button>
        </div>
      </form>
    </div>
  );
}
