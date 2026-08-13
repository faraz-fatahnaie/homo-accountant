"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PROJECT_STATUS_LABELS, projectsApi, type ProjectStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatRials, formatJalaliLong } from "@/lib/format";
import { Badge, ErrorBlock, LoadingBlock } from "@/components/ui";

const STATUS_TONES: Record<ProjectStatus, "success" | "muted" | "warn"> = {
  active: "success",
  completed: "muted",
  on_hold: "warn",
};

export default function ProjectsPage() {
  const { isWriter } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(),
  });

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");
  const [status, setStatus] = useState<ProjectStatus>("active");
  const [responsible, setResponsible] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      projectsApi.create({
        name: name.trim(),
        budget: Number(budget.replace(/[^\d]/g, "")) || 0,
        status,
        responsible_person: responsible.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      setShowForm(false);
      setName("");
      setBudget("");
      setStatus("active");
      setResponsible("");
    },
    onError: (err) => setFormError(err instanceof Error ? err.message : "خطای ناشناخته"),
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">پروژهها</h1>
          <p className="mt-0.5 text-xs text-muted">
            بودجه و وضعیت پروژهها — {(data ?? []).length} پروژه
          </p>
        </div>
        {isWriter ? (
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "بستن" : "+ پروژه جدید"}
          </button>
        ) : null}
      </div>

      {showForm && isWriter ? (
        <form
          className="card mb-4 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            setFormError(null);
            if (!name.trim()) {
              setFormError("نام پروژه الزامی است");
              return;
            }
            createMutation.mutate();
          }}
        >
          <div className="grid gap-3 md:grid-cols-4">
            <div>
              <label className="label" htmlFor="p-name">نام <span className="text-danger">*</span></label>
              <input id="p-name" className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="p-budget">بودجه (ریال)</label>
              <input id="p-budget" className="input" dir="ltr" inputMode="numeric" value={budget}
                onChange={(e) => setBudget(e.target.value)} placeholder="۵۰۰٬۰۰۰٬۰۰۰" />
            </div>
            <div>
              <label className="label" htmlFor="p-status">وضعیت</label>
              <select id="p-status" className="input" value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>
                {(Object.keys(PROJECT_STATUS_LABELS) as ProjectStatus[]).map((s) => (
                  <option key={s} value={s}>{PROJECT_STATUS_LABELS[s]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p-owner">مسئول</label>
              <input id="p-owner" className="input" value={responsible} onChange={(e) => setResponsible(e.target.value)} />
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
          هنوز پروژهای ثبت نشده است.
        </div>
      ) : null}

      {data && data.length > 0 ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-right text-sm">
              <thead>
                <tr className="border-b-2 border-border-strong bg-surface-2 text-[11px] font-extrabold text-muted">
                  <th className="px-3 py-2.5">نام</th>
                  <th className="px-3 py-2.5">وضعیت</th>
                  <th className="px-3 py-2.5">مسئول</th>
                  <th className="px-3 py-2.5">تاریخ شروع</th>
                  <th className="px-3 py-2.5 text-left">بودجه (ریال)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dashed divide-border">
                {data.map((p) => (
                  <tr key={p.id} className="hover:bg-[var(--row-hover)]">
                    <td className="px-3 py-2.5 font-bold">{p.name}</td>
                    <td className="px-3 py-2.5">
                      <Badge tone={STATUS_TONES[p.status]}>{PROJECT_STATUS_LABELS[p.status]}</Badge>
                    </td>
                    <td className="px-3 py-2.5 text-muted">{p.responsible_person ?? "—"}</td>
                    <td className="px-3 py-2.5 text-muted">
                      {p.start_date ? formatJalaliLong(new Date(p.start_date + "T12:00:00")) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-left font-bold tabular-nums">
                      {formatRials(p.budget)}
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
