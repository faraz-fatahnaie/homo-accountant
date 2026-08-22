"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  accountsApi,
  ApiError,
  billsApi,
  contactsApi,
  projectsApi,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalali, parseAmount, parseJalaliInput, todayJalali } from "@/lib/format";

export default function NewBillPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isWriter, loading: authLoading } = useAuth();

  const [vendorId, setVendorId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [accountCode, setAccountCode] = useState("");
  const [issueDate, setIssueDate] = useState(() => {
    const [jy, jm, jd] = todayJalali();
    return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  });
  const [dueDate, setDueDate] = useState("");
  const [billNumber, setBillNumber] = useState("");
  const [memo, setMemo] = useState("");
  const [total, setTotal] = useState("");
  const [postAfter, setPostAfter] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { data: accounts } = useQuery({ queryKey: ["accounts"], queryFn: accountsApi.list });
  const { data: vendors } = useQuery({ queryKey: ["contacts"], queryFn: () => contactsApi.list(true) });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: () => projectsApi.list(true) });

  useEffect(() => {
    if (!authLoading && !isWriter) router.replace("/bills");
  }, [authLoading, isWriter, router]);

  const expenseAccounts = useMemo(
    () => (accounts ?? []).filter((a) => a.is_active && a.type === "expense"),
    [accounts],
  );
  const vendorList = useMemo(
    () => (vendors ?? []).filter((c) => c.roles.includes("vendor") || c.roles.includes("other")),
    [vendors],
  );

  const createMutation = useMutation({
    mutationFn: async () => {
      const issue = parseJalaliInput(issueDate);
      if (!issue) throw new ApiError(422, { error: { code: "invalid_date", message: "تاریخ فاکتور نامعتبر است" } });
      let due = dueDate ? parseJalaliInput(dueDate) : null;
      if (!due) due = new Date(issue.getTime() + 30 * 24 * 3600 * 1000);
      const amount = parseAmount(total);
      if (!Number.isFinite(amount) || amount <= 0) {
        throw new ApiError(422, { error: { code: "invalid_amount", message: "مبلغ معتبر وارد کنید" } });
      }
      if (!accountCode) throw new ApiError(422, { error: { code: "no_account", message: "حساب هزینه را انتخاب کنید" } });
      if (!vendorId) throw new ApiError(422, { error: { code: "no_vendor", message: "تأمین‌کننده را انتخاب کنید" } });
      const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      return billsApi.create({
        vendor_id: Number(vendorId),
        project_id: projectId ? Number(projectId) : null,
        account_code: accountCode,
        issue_date: fmt(issue),
        due_date: fmt(due),
        bill_number: billNumber.trim() || null,
        memo: memo.trim(),
        total: amount,
      });
    },
    onSuccess: async (bill) => {
      if (postAfter) {
        await billsApi.post(bill.id);
      }
      void queryClient.invalidateQueries({ queryKey: ["bills", "entries", "balances"] });
      router.push("/bills");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "خطای ناشناخته"),
  });

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">فاکتور خرید جدید</h1>
        <p className="mt-0.5 text-xs text-muted">
          پس از ایجاد، «ثبت نهایی» سند «هزینه ← پرداختنی» را در دفتر کل می‌نویسد
        </p>
      </div>

      <form
        className="card p-5"
        onSubmit={(e) => { e.preventDefault(); setError(null); createMutation.mutate(); }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="label" htmlFor="b-vendor">تأمین‌کننده <span className="text-danger">*</span></label>
            <select id="b-vendor" className="input" value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
              <option value="">انتخاب تأمین‌کننده…</option>
              {vendorList.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="b-project">پروژه</label>
            <select id="b-project" className="input" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">بدون پروژه</option>
              {(projects ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="b-account">حساب هزینه <span className="text-danger">*</span></label>
            <select id="b-account" className="input" value={accountCode} onChange={(e) => setAccountCode(e.target.value)}>
              <option value="">انتخاب حساب…</option>
              {expenseAccounts.map((a) => (
                <option key={a.id} value={a.code}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="b-total">مبلغ (ریال) <span className="text-danger">*</span></label>
            <input id="b-total" className="input tabular-nums" dir="ltr" inputMode="numeric" value={total}
              onChange={(e) => setTotal(e.target.value)} placeholder="۴۸٬۵۰۰٬۰۰۰" />
            <p className="mt-1 text-[11px] text-muted">رقم فارسی یا انگلیسی، با یا بدون جداکننده</p>
          </div>
          <div>
            <label className="label" htmlFor="b-issue">تاریخ فاکتور (شمسی) <span className="text-danger">*</span></label>
            <input id="b-issue" className="input" dir="ltr" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
            <p className="mt-1 text-[11px] text-muted">امروز: {formatJalali(new Date())}</p>
          </div>
          <div>
            <label className="label" htmlFor="b-due">سررسید (شمسی)</label>
            <input id="b-due" className="input" dir="ltr" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
              placeholder="خالی = ۳۰ روز بعد" />
          </div>
          <div>
            <label className="label" htmlFor="b-number">شماره فاکتور تأمین‌کننده</label>
            <input id="b-number" className="input" dir="ltr" value={billNumber} onChange={(e) => setBillNumber(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="b-memo">شرح <span className="text-danger">*</span></label>
            <input id="b-memo" className="input" value={memo} onChange={(e) => setMemo(e.target.value)}
              placeholder="مثلاً: خرید ورق فولادی ۲ تن" />
          </div>
        </div>

        {error ? <p className="error mt-3" role="alert">{error}</p> : null}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? "در حال ثبت…" : "ایجاد فاکتور خرید"}
          </button>
          <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
            <input type="checkbox" className="h-4 w-4 accent-[var(--primary)]" checked={postAfter}
              onChange={(e) => setPostAfter(e.target.checked)} />
            بلافاصله ثبت نهایی (سند پرداختنی)
          </label>
          <button type="button" className="btn btn-ghost" onClick={() => router.push("/bills")}>انصراف</button>
        </div>
      </form>
    </div>
  );
}
