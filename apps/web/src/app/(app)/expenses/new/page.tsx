"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  accountsApi,
  ApiError,
  contactsApi,
  expensesApi,
  PAYMENT_METHOD_LABELS,
  projectsApi,
  type PaymentMethod,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalali, parseAmount, parseJalaliInput, todayJalali } from "@/lib/format";

export default function NewExpensePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { canDraft, loading: authLoading } = useAuth();

  const [dateInput, setDateInput] = useState(() => {
    const [jy, jm, jd] = todayJalali();
    return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  });
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [accountCode, setAccountCode] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [contactId, setContactId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [postAfter, setPostAfter] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<{ name: string; size: number }[]>([]);

  const { data: accounts } = useQuery({ queryKey: ["accounts"], queryFn: accountsApi.list });
  const { data: contacts } = useQuery({ queryKey: ["contacts"], queryFn: () => contactsApi.list() });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: () => projectsApi.list() });

  useEffect(() => {
    if (!authLoading && !canDraft) router.replace("/expenses");
  }, [authLoading, canDraft, router]);

  const expenseAccounts = useMemo(
    () => (accounts ?? []).filter((a) => a.is_active && a.type === "expense"),
    [accounts],
  );

  const createMutation = useMutation({
    mutationFn: async () => {
      const date = parseJalaliInput(dateInput);
      if (!date) throw new ApiError(422, { error: { code: "invalid_date", message: "تاریخ شمسی نامعتبر است" } });
      const parsedAmount = parseAmount(amount);
      if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
        throw new ApiError(422, { error: { code: "invalid_amount", message: "مبلغ معتبر وارد کنید" } });
      }
      if (!description.trim()) {
        throw new ApiError(422, { error: { code: "no_description", message: "شرح هزینه را بنویسید" } });
      }
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, "0");
      const d = String(date.getDate()).padStart(2, "0");
      return expensesApi.create({
        entry_date: `${y}-${m}-${d}`,
        account_code: accountCode,
        amount: parsedAmount,
        payment_method: paymentMethod,
        contact_id: contactId ? Number(contactId) : null,
        project_id: projectId ? Number(projectId) : null,
        reference: reference.trim() || null,
        description: description.trim(),
        notes: notes.trim() || null,
        idempotency_key: `ui-exp-${Date.now()}`,
      });
    },
    onSuccess: async (expense) => {
      // upload any pending files, then (optionally) post
      for (const file of pendingFiles) {
        try {
          await expensesApi.uploadAttachment(expense.id, file);
        } catch {
          /* keep going; attachment failure isn't fatal to the expense */
        }
      }
      if (postAfter) {
        await expensesApi.post(expense.id);
      }
      void queryClient.invalidateQueries({ queryKey: ["expenses"] }); void queryClient.invalidateQueries({ queryKey: ["entries"] }); void queryClient.invalidateQueries({ queryKey: ["balances"] });
      router.push("/expenses");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "خطای ناشناخته"),
  });

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  function onFilePick(fileList: FileList | null) {
    if (!fileList) return;
    const files = Array.from(fileList);
    setPendingFiles((prev) => [...prev, ...files]);
    setUploads((prev) => [
      ...prev,
      ...files.map((f) => ({ name: f.name, size: f.size })),
    ]);
  }

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">ثبت هزینه جدید</h1>
        <p className="mt-0.5 text-xs text-muted">
          پیشنویس میسازد؛ پس از ایجاد میتوانید «ثبت نهایی» کنید تا سند وارد دفتر کل شود
        </p>
      </div>

      <form
        className="card p-5"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          if (!accountCode) {
            setError("حساب هزینه را انتخاب کنید");
            return;
          }
          createMutation.mutate();
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="label" htmlFor="ex-date">تاریخ (شمسی) <span className="text-danger">*</span></label>
            <input id="ex-date" className="input" dir="ltr" value={dateInput} onChange={(e) => setDateInput(e.target.value)} />
            <p className="mt-1 text-[11px] text-muted">امروز: {formatJalali(new Date())}</p>
          </div>
          <div>
            <label className="label" htmlFor="ex-amount">مبلغ (ریال) <span className="text-danger">*</span></label>
            <input id="ex-amount" className="input tabular-nums" dir="ltr" inputMode="numeric" value={amount}
              onChange={(e) => setAmount(e.target.value)} placeholder="۴۸٬۵۰۰٬۰۰۰" />
            <p className="mt-1 text-[11px] text-muted">رقم فارسی یا انگلیسی، با یا بدون جداکننده</p>
          </div>
          <div>
            <label className="label" htmlFor="ex-account">حساب هزینه <span className="text-danger">*</span></label>
            <select id="ex-account" className="input" value={accountCode} onChange={(e) => setAccountCode(e.target.value)}>
              <option value="">انتخاب حساب…</option>
              {expenseAccounts.map((a) => (
                <option key={a.id} value={a.code}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="ex-pay">روش پرداخت</label>
            <select id="ex-pay" className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}>
              {(Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[]).map((m) => (
                <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-muted">
              {paymentMethod === "cash" ? "از صندوق (۱۰۱) پرداخت میشود" : "از بانک (۱۰۲) پرداخت میشود"}
            </p>
          </div>
          <div>
            <label className="label" htmlFor="ex-contact">طرف حساب</label>
            <select id="ex-contact" className="input" value={contactId} onChange={(e) => setContactId(e.target.value)}>
              <option value="">بدون طرف حساب</option>
              {(contacts ?? []).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="ex-project">پروژه</label>
            <select id="ex-project" className="input" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">بدون پروژه</option>
              {(projects ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="ex-ref">شماره پیگیری / مرجع</label>
            <input id="ex-ref" className="input" dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="ex-notes">توضیحات</label>
            <input id="ex-notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <label className="label" htmlFor="ex-desc">شرح <span className="text-danger">*</span></label>
            <input id="ex-desc" className="input" value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder="مثلاً: خرید کامپیوتر اداری" />
          </div>
          <div className="md:col-span-2">
            <span className="label">پیوست (فاکتور/رسید — تصویر یا PDF تا ۵ مگابایت)</span>
            <label className="block cursor-pointer rounded-md border-2 border-dashed border-border-strong bg-surface-2 px-4 py-6 text-center text-sm text-muted hover:border-primary">
              <input type="file" className="hidden" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" multiple
                onChange={(e) => onFilePick(e.target.files)} />
              کلیک کنید یا فایل را اینجا رها کنید
            </label>
            {uploads.length > 0 ? (
              <ul className="mt-2 space-y-1">
                {uploads.map((u, i) => (
                  <li key={i} className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-xs">
                    <span className="font-bold" dir="ltr">{u.name}</span>
                    <span className="text-muted">({Math.round(u.size / 1024)} کیلوبایت)</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>

        {error ? <p className="error mt-3" role="alert">{error}</p> : null}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? "در حال ثبت…" : "ایجاد هزینه"}
          </button>
          <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
            <input type="checkbox" className="h-4 w-4 accent-[var(--primary)]" checked={postAfter}
              onChange={(e) => setPostAfter(e.target.checked)} />
            بلافاصله ثبت نهایی (ایجاد سند در دفتر کل)
          </label>
          <button type="button" className="btn btn-ghost" onClick={() => router.push("/expenses")}>
            انصراف
          </button>
        </div>
      </form>
    </div>
  );
}
