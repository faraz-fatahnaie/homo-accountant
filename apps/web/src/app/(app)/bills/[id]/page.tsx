"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { billsApi, BILL_STATUS_LABELS, PAYMENT_METHOD_LABELS, type PaymentMethod } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalaliLong, formatRials, parseAmount, parseJalaliInput, todayJalali } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

export default function BillDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isWriter } = useAuth();
  const id = Number(params.id);

  const { data: bill, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["bills", id],
    queryFn: () => billsApi.detail(id),
  });

  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState<PaymentMethod>("cash");
  const [payRef, setPayRef] = useState("");
  const [payDate, setPayDate] = useState(() => {
    const [jy, jm, jd] = todayJalali();
    return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  });
  const [payError, setPayError] = useState<string | null>(null);

  const postMutation = useMutation({
    mutationFn: () => billsApi.post(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["bills"] });
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
      if (!Number.isFinite(amount) || amount <= 0) throw new Error("مبلغ معتبر وارد کنید");
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, "0");
      const d = String(date.getDate()).padStart(2, "0");
      const body: { amount: number; paid_at: string; method: PaymentMethod; reference?: string } = {
        amount,
        paid_at: `${y}-${m}-${d}`,
        method: payMethod,
      };
      if (payRef.trim()) body.reference = payRef.trim();
      return billsApi.pay(id, body);
    },
    onSuccess: () => {
      setPayAmount("");
      setPayRef("");
      setPayError(null);
      void queryClient.invalidateQueries({ queryKey: ["bills"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
    onError: (e) => setPayError(e instanceof Error ? e.message : "خطا"),
  });
  const voidMutation = useMutation({
    mutationFn: () => billsApi.voidEntry(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["bills"] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["balances"] });
    },
    onError: (e) => setPayError(e instanceof Error ? e.message : "خطا"),
  });

  if (isLoading) return <LoadingBlock />;
  if (isError || !bill) {
    return <ErrorBlock message={error instanceof Error ? error.message : "فاکتور خرید یافت نشد"} onRetry={() => void refetch()} />;
  }

  const canPay = bill.status === "open" || bill.status === "partially_paid";

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">فاکتور خرید {bill.number ?? "پیش‌نویس"}</h1>
          <p className="mt-0.5 text-xs text-muted">
            {bill.vendor_name} · صدور {formatJalaliLong(new Date(bill.issue_date + "T12:00:00"))} · سررسید{" "}
            {formatJalaliLong(new Date(bill.due_date + "T12:00:00"))}
            {bill.bill_number ? <span className="mr-2" dir="ltr">شماره تأمین‌کننده: {bill.bill_number}</span> : null}
            {bill.is_overdue ? " · معوق" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {bill.status === "draft" && isWriter ? (
            <button className="btn btn-primary" disabled={postMutation.isPending} onClick={() => postMutation.mutate()}>
              ثبت نهایی (سند پرداختنی)
            </button>
          ) : null}
          <button className="btn btn-ghost" onClick={() => router.push("/bills")}>بازگشت</button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        <Badge tone={bill.status === "paid" ? "success" : bill.status === "void" ? "danger" : bill.status === "draft" ? "muted" : bill.is_overdue ? "danger" : "info"}>
          {BILL_STATUS_LABELS[bill.status]}
        </Badge>
        <span className="text-muted">حساب: <b dir="ltr">{bill.account_code}</b> {bill.account_name}</span>
        <span className="text-muted">مبلغ: <b className="tabular-nums">{formatRials(bill.total)}</b> ریال</span>
        <span className="text-muted">پرداخت‌شده: <b className="tabular-nums">{formatRials(bill.paid_total)}</b></span>
        <span className={bill.balance > 0 ? "font-bold text-danger-strong" : "text-muted"}>
          مانده: <b className="tabular-nums">{formatRials(bill.balance)}</b> ریال
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <div className="card-head"><h2 className="text-sm font-extrabold">شرح</h2></div>
          <p className="px-4 py-4 text-sm leading-6">{bill.memo}</p>
        </section>

        <section className="card">
          <div className="card-head"><h2 className="text-sm font-extrabold">پرداخت‌ها</h2></div>
          <div className="px-4 py-2">
            {bill.payments.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted">پرداختی ثبت نشده است.</p>
            ) : (
              <ul className="divide-y divide-dashed divide-border">
                {bill.payments.map((p) => (
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

          {canPay && isWriter ? (
            <form
              className="border-t border-border p-4"
              onSubmit={(e) => { e.preventDefault(); setPayError(null); payMutation.mutate(); }}
            >
              <h3 className="mb-2 text-xs font-extrabold text-muted">ثبت پرداخت</h3>
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

          {canPay && isWriter ? (
            <div className="border-t border-border p-4">
              <button className="btn btn-danger-ghost" disabled={voidMutation.isPending}
                onClick={() => { if (window.confirm("فاکتور خرید باطل شود؟ (فقط بدون پرداخت)")) voidMutation.mutate(); }}>
                باطل کردن فاکتور
              </button>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
