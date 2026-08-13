"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CONTACT_ROLE_LABELS, contactsApi, type ContactRole } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { faDigits } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

const ALL_ROLES = Object.keys(CONTACT_ROLE_LABELS) as ContactRole[];

export default function ContactsPage() {
  const { isWriter } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["contacts"],
    queryFn: () => contactsApi.list(),
  });

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [roles, setRoles] = useState<ContactRole[]>(["customer"]);
  const [phone, setPhone] = useState("");
  const [terms, setTerms] = useState("0");
  const [formError, setFormError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      contactsApi.create({
        name: name.trim(),
        roles,
        phone: phone.trim() || null,
        payment_terms_days: Number(terms) || 0,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
      setShowForm(false);
      setName("");
      setRoles(["customer"]);
      setPhone("");
      setTerms("0");
    },
    onError: (err) => setFormError(err instanceof Error ? err.message : "خطای ناشناخته"),
  });

  function toggleRole(role: ContactRole) {
    setRoles((prev) => (prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]));
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">طرف حسابها</h1>
          <p className="mt-0.5 text-xs text-muted">
            مشتری، تأمینکننده، سرمایهگذار، بانک و… — {(data ?? []).length} طرف حساب
          </p>
        </div>
        {isWriter ? (
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "بستن" : "+ طرف حساب جدید"}
          </button>
        ) : null}
      </div>

      {showForm && isWriter ? (
        <form
          className="card mb-4 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            setFormError(null);
            if (roles.length === 0) {
              setFormError("حداقل یک نقش انتخاب کنید");
              return;
            }
            createMutation.mutate();
          }}
        >
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <label className="label" htmlFor="c-name">نام <span className="text-danger">*</span></label>
              <input id="c-name" className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="c-phone">تلفن</label>
              <input id="c-phone" className="input" dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="c-terms">شرایط پرداخت (روز)</label>
              <input id="c-terms" className="input" dir="ltr" inputMode="numeric" value={terms}
                onChange={(e) => setTerms(e.target.value.replace(/[^\d]/g, ""))} />
            </div>
          </div>
          <div className="mt-3">
            <span className="label">نقشها</span>
            <div className="flex flex-wrap gap-2">
              {ALL_ROLES.map((role) => (
                <label key={role} className={`chip cursor-pointer ${roles.includes(role) ? "active" : ""}`}>
                  <input
                    type="checkbox"
                    className="hidden"
                    checked={roles.includes(role)}
                    onChange={() => toggleRole(role)}
                  />
                  {CONTACT_ROLE_LABELS[role]}
                </label>
              ))}
            </div>
          </div>
          {formError ? <p className="error mt-2" role="alert">{formError}</p> : null}
          <button type="submit" className="btn btn-primary mt-3" disabled={createMutation.isPending}>
            ایجاد
          </button>
        </form>
      ) : null}

      {isLoading ? <LoadingBlock /> : null}
      {isError ? <ErrorBlock message={error instanceof Error ? error.message : "خطا"} onRetry={() => void refetch()} /> : null}

      {data && data.length === 0 ? (
        <div className="card px-4 py-10 text-center text-sm text-muted">
          هنوز طرف حسابی ثبت نشده است.
          {isWriter ? " با دکمه «+ طرف حساب جدید» شروع کنید." : null}
        </div>
      ) : null}

      {data && data.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.map((c) => (
            <div key={c.id} className="card p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="font-extrabold">{c.name}</div>
                {!c.is_active ? <Badge tone="danger">غیرفعال</Badge> : null}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {c.roles.map((r) => (
                  <Badge key={r} tone="info">
                    {CONTACT_ROLE_LABELS[r as ContactRole] ?? r}
                  </Badge>
                ))}
              </div>
              <div className="mt-3 space-y-1 text-xs text-muted">
                {c.phone ? <div dir="ltr" className="text-right">{faDigits(c.phone)}</div> : null}
                {c.email ? <div dir="ltr" className="text-right">{c.email}</div> : null}
                <div>شرایط پرداخت: {faDigits(c.payment_terms_days)} روز</div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
