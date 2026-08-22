"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  invoicesApi,
  INVOICE_STATUS_LABELS,
  PAYMENT_METHOD_LABELS,
  type PaymentMethod,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalaliLong, formatRials, parseAmount, parseJalaliInput, todayJalali } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isWriter } = useAuth();
  const id = Number(params.id);

  const { data: inv, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["invoices", id],
    queryFn: () => invoicesApi.detail(id),
  });

  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState<PaymentMethod>("cash");
  const [payRef, setPayRef] = useState("");
  const [payError, setPayError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const issueMutation = useMutation({
    mutationFn: () => invoicesApi.issue(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
    onError: (e) => setPayError(e instanceof Error ? e.message : "خطا"),
  });
  const payMutation = useMutation({
    mutationFn: () => {
      const date = parseJalaliInput(payDate);
      if (!date) throw new Error("تاریخ پرداخت شمسی نامعتبر است");
      const amount = parseAmount(payAmount);
      if (!Number.isFinite(amount) || amount <= 0) {
        throw new Error("مبلغ معتبر وارد کنید");
      }
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, "0");
      const d = String(date.getDate()).padStart(2, "0");
      const body: { amount: number; paid_at: string; method: PaymentMethod; reference?: string } = {
        amount,
        paid_at: `${y}-${m}-${d}`,
        method: payMethod,
      };
      if (payRef.trim()) body.reference = payRef.trim();
      return invoicesApi.pay(id, body);
    },
    onSuccess: () => {
      setPayAmount("");
      setPayRef("");
      setPayError(null);
      void queryClient.invalidateQueries({ queryKey: ["invoices"] }); void queryClient.invalidateQueries({ queryKey: ["entries"] }); void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
    onError: (e) => setPayError(e instanceof Error ? e.message : "خطا"),
  });
  const voidMutation = useMutation({
    mutationFn: () => invoicesApi.voidEntry(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
    onError: (e) => setPayError(e instanceof Error ? e.message : "خطا"),
  });

  const [payDate, setPayDate] = useState(() => {
    const [jy, jm, jd] = todayJalali();
    return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  });

  if (isLoading) return <LoadingBlock />;
  if (isError || !inv) {
    return <ErrorBlock message={error instanceof Error ? error.message : "صورت‌حساب یافت نشد"} onRetry={() => void refetch()} />;
  }

  const canReceivePayment = inv.status === "issued" || inv.status === "partially_paid";

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">صورت‌حساب {inv.number ?? "پیش‌نویس"}</h1>
          <p className="mt-0.5 text-xs text-muted">
            {inv.customer_name} · صدور {formatJalaliLong(new Date(inv.issue_date + "T12:00:00"))} · سررسید{" "}
            {formatJalaliLong(new Date(inv.due_date + "T12:00:00"))}
            {inv.is_overdue ? " · معوق" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {inv.status === "draft" && isWriter ? (
            <button className="btn btn-primary" disabled={issueMutation.isPending} onClick={() => issueMutation.mutate()}>
              صدور صورت‌حساب
            </button>
          ) : null}
          {inv.status !== "draft" && inv.status !== "void" ? (
            <button
              className="btn btn-ghost"
              onClick={() => {
                setPdfError(null);
                void invoicesApi
                  .downloadPdf(inv.id, `invoice-${inv.number ?? inv.id}.pdf`)
                  .catch((downloadError: unknown) => {
                    setPdfError(downloadError instanceof Error ? downloadError.message : "دانلود PDF انجام نشد");
                  });
              }}
            >
              دانلود PDF
            </button>
          ) : null}
          <button className="btn btn-ghost" onClick={() => router.push("/invoices")}>بازگشت</button>
        </div>
      </div>
      {pdfError ? <div className="mb-4"><ErrorBlock message={pdfError} /></div> : null}

      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        <Badge tone={inv.status === "paid" ? "success" : inv.status === "void" ? "danger" : inv.status === "draft" ? "muted" : inv.is_overdue ? "danger" : "info"}>
          {INVOICE_STATUS_LABELS[inv.status]}
        </Badge>
        <span className="text-muted">جمع کل: <b className="tabular-nums">{formatRials(inv.total)}</b> ریال</span>
        <span className="text-muted">پرداخت‌شده: <b className="tabular-nums">{formatRials(inv.paid_total)}</b></span>
        <span className={inv.balance > 0 ? "font-bold text-danger-strong" : "text-muted"}>
          مانده: <b className="tabular-nums">{formatRials(inv.balance)}</b> ریال
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* items */}
        <section className="card">
          <div className="card-head"><h2 className="text-sm font-extrabold">ردیف‌ها</h2></div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead>
                <tr className="border-b border-border text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2 text-right">شرح</th>
                  <th className="px-3 py-2 text-left">تعداد</th>
                  <th className="px-3 py-2 text-left">قیمت واحد</th>
                  <th className="px-3 py-2 text-left">تخفیف</th>
                  <th className="px-3 py-2 text-left">مبلغ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {inv.items.map((it) => (
                  <tr key={it.id}>
                    <td className="px-3 py-2">{it.description}</td>
                    <td className="px-3 py-2 tabular-nums">{it.quantity}</td>
                    <td className="px-3 py-2 tabular-nums">{formatRials(it.unit_price)}</td>
                    <td className="px-3 py-2 tabular-nums">{it.discount ? formatRials(it.discount) : "—"}</td>
                    <td className="px-3 py-2 text-left font-bold tabular-nums">{formatRials(it.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {inv.notes ? <p className="px-4 py-3 text-xs text-muted">{inv.notes}</p> : null}
          {inv.payment_instructions ? (
            <p className="border-t border-border px-4 py-3 text-xs text-muted">دستور پرداخت: {inv.payment_instructions}</p>
          ) : null}
        </section>

        {/* payments */}
        <section className="card">
          <div className="card-head"><h2 className="text-sm font-extrabold">پرداخت‌ها</h2></div>
          <div className="px-4 py-2">
            {inv.payments.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted">پرداختی ثبت نشده است.</p>
            ) : (
              <ul className="divide-y divide-dashed divide-border">
                {inv.payments.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                    <span>
                      {PAYMENT_METHOD_LABELS[p.method as PaymentMethod] ?? p.method} ·{" "}
                      {formatJalaliLong(new Date(p.paid_at + "T12:00:00"))}
                      {p.reference ? <span className="mr-2 text-xs text-muted" dir="ltr">{p.reference}</span> : null}
                    </span>
                    <b className="tabular-nums">{formatRials(p.amount)}</b>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {canReceivePayment && isWriter ? (
            <form
              className="border-t border-border p-4"
              onSubmit={(e) => { e.preventDefault(); setPayError(null); payMutation.mutate(); }}
            >
              <h3 className="mb-2 text-xs font-extrabold text-muted">ثبت پرداخت دریافتی</h3>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                <input className="input tabular-nums" dir="ltr" inputMode="numeric" placeholder="مبلغ (ریال)"
                  aria-label="مبلغ پرداخت" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} />
                <input className="input" dir="ltr" aria-label="تاریخ پرداخت (شمسی)" value={payDate}
                  onChange={(e) => setPayDate(e.target.value)} />
                <select className="input" aria-label="روش پرداخت" value={payMethod}
                  onChange={(e) => setPayMethod(e.target.value as PaymentMethod)}>
                  {(Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[]).map((m) => (
                    <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>
                  ))}
                </select>
                <input className="input" dir="ltr" aria-label="کد پیگیری پرداخت" placeholder="کد پیگیری"
                  value={payRef} onChange={(e) => setPayRef(e.target.value)} />
                <button type="submit" className="btn btn-primary" disabled={payMutation.isPending}>ثبت پرداخت</button>
              </div>
              {payError ? <p className="error mt-2" role="alert">{payError}</p> : null}
            </form>
          ) : null}

          {(inv.status === "issued" || inv.status === "partially_paid") && isWriter ? (
            <div className="border-t border-border p-4">
              <button className="btn btn-danger-ghost" disabled={voidMutation.isPending}
                onClick={() => { if (window.confirm("صورت‌حساب باطل شود؟ (فقط بدون پرداخت)")) voidMutation.mutate(); }}>
                باطل کردن صورت‌حساب
              </button>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
