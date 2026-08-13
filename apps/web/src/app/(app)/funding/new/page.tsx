"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, contactsApi, fundingApi, FUNDING_TYPE_LABELS, type FundingType } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatJalali, parseAmount, parseJalaliInput, todayJalali } from "@/lib/format";

export default function NewFundingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isWriter, loading: authLoading } = useAuth();

  const [fundingType, setFundingType] = useState<FundingType>("investment");
  const [contactId, setContactId] = useState("");
  const [eventDate, setEventDate] = useState(() => {
    const [jy, jm, jd] = todayJalali();
    return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  });
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<"cash" | "bank" | "online">("bank");
  const [agreementRef, setAgreementRef] = useState("");
  const [maturityDate, setMaturityDate] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: contacts } = useQuery({ queryKey: ["contacts"], queryFn: () => contactsApi.list(true) });
  const { data: mappings } = useQuery({ queryKey: ["funding-mappings"], queryFn: fundingApi.mappings });

  useEffect(() => {
    if (!authLoading && !isWriter) router.replace("/funding");
  }, [authLoading, isWriter, router]);

  const relevantContacts = useMemo(() => {
    const roleMap: Record<FundingType, string[]> = {
      investment: ["investor"],
      loan: ["lender"],
      grant: ["grantor"],
      revenue: ["customer", "other"],
    };
    const roles = roleMap[fundingType];
    return (contacts ?? []).filter((c) => c.roles.some((r) => roles.includes(r)));
  }, [contacts, fundingType]);

  const mappedAccount = useMemo(
    () => mappings?.find((m) => m.funding_type === fundingType)?.account_code ?? "—",
    [mappings, fundingType],
  );

  const createMutation = useMutation({
    mutationFn: async () => {
      const date = parseJalaliInput(eventDate);
      if (!date) throw new ApiError(422, { error: { code: "invalid_date", message: "تاریخ نامعتبر است" } });
      const amt = parseAmount(amount);
      if (!Number.isFinite(amt) || amt <= 0) throw new ApiError(422, { error: { code: "invalid_amount", message: "مبلغ معتبر وارد کنید" } });
      let maturity = null;
      if (fundingType === "loan") {
        maturity = maturityDate ? parseJalaliInput(maturityDate) : null;
        if (!maturity) throw new ApiError(422, { error: { code: "loan_maturity_required", message: "برای وام، تاریخ سررسید الزامی است" } });
      }
      const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      return fundingApi.create({
        funding_type: fundingType,
        contact_id: contactId ? Number(contactId) : null,
        event_date: fmt(date),
        amount: amt,
        method,
        agreement_ref: agreementRef.trim() || null,
        maturity_date: maturity ? fmt(maturity) : null,
        notes: notes.trim() || null,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["funding", "entries", "balances"] });
      router.push("/funding");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "خطای ناشناخته"),
  });

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">رویداد تأمین مالی جدید</h1>
        <p className="mt-0.5 text-xs text-muted">
          با ثبت، سند «نقد/بانک ← حساب نگاشتشده» در دفتر کل نوشته میشود
        </p>
      </div>

      <form className="card p-5" onSubmit={(e) => { e.preventDefault(); setError(null); createMutation.mutate(); }}>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="label" htmlFor="f-type">نوع تأمین مالی <span className="text-danger">*</span></label>
            <select id="f-type" className="input" value={fundingType} onChange={(e) => setFundingType(e.target.value as FundingType)}>
              {(Object.keys(FUNDING_TYPE_LABELS) as FundingType[]).map((t) => (
                <option key={t} value={t}>{FUNDING_TYPE_LABELS[t]}</option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-muted">حساب نگاشت: <b dir="ltr">{mappedAccount}</b></p>
          </div>
          <div>
            <label className="label" htmlFor="f-contact">طرف حساب</label>
            <select id="f-contact" className="input" value={contactId} onChange={(e) => setContactId(e.target.value)}>
              <option value="">بدون طرف حساب</option>
              {relevantContacts.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="f-amount">مبلغ (ریال) <span className="text-danger">*</span></label>
            <input id="f-amount" className="input tabular-nums" dir="ltr" inputMode="numeric" value={amount}
              onChange={(e) => setAmount(e.target.value)} placeholder="۱۰۰٬۰۰۰٬۰۰۰" />
          </div>
          <div>
            <label className="label" htmlFor="f-method">روش دریافت</label>
            <select id="f-method" className="input" value={method} onChange={(e) => setMethod(e.target.value as "cash" | "bank" | "online")}>
              <option value="bank">انتقال بانکی (۱۰۲)</option>
              <option value="cash">نقدی (۱۰۱)</option>
              <option value="online">درگاه آنلاین (۱۰۲)</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="f-date">تاریخ (شمسی) <span className="text-danger">*</span></label>
            <input id="f-date" className="input" dir="ltr" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
            <p className="mt-1 text-[11px] text-muted">امروز: {formatJalali(new Date())}</p>
          </div>
          {fundingType === "loan" ? (
            <div>
              <label className="label" htmlFor="f-maturity">سررسید وام (شمسی) <span className="text-danger">*</span></label>
              <input id="f-maturity" className="input" dir="ltr" value={maturityDate} onChange={(e) => setMaturityDate(e.target.value)} />
            </div>
          ) : null}
          <div>
            <label className="label" htmlFor="f-ref">مرجع / شماره توافق</label>
            <input id="f-ref" className="input" dir="ltr" value={agreementRef} onChange={(e) => setAgreementRef(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="f-notes">یادداشت</label>
            <input id="f-notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>

        {error ? <p className="error mt-3" role="alert">{error}</p> : null}

        <div className="mt-5 flex items-center gap-3">
          <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? "در حال ثبت…" : "ثبت رویداد"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => router.push("/funding")}>انصراف</button>
        </div>
      </form>
    </div>
  );
}
