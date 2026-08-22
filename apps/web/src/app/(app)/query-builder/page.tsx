"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ApiError,
  queryBuilderApi,
  type QueryDataset,
  type QueryTemplate,
} from "@/lib/api";
import { formatRials, faDigits } from "@/lib/format";
import { LoadingBlock } from "@/components/ui";

const OP_LABELS: Record<string, string> = {
  eq: "برابر با",
  ne: "نامساوی با",
  gt: "بزرگتر از",
  gte: "بزرگتر یا مساوی",
  lt: "کوچکتر از",
  lte: "کوچکتر یا مساوی",
  contains: "شامل عبارت",
  in: "در فهرست",
};

const VALUE_LABELS: Record<string, string> = {
  draft: "پیش‌نویس",
  posted: "ثبت‌شده",
  voided: "برگشتی",
  issued: "صادرشده",
  partially_paid: "پرداخت‌شده جزئی",
  paid: "پرداخت‌شده",
  void: "باطل‌شده",
  open: "باز",
  cash: "نقدی",
  bank: "انتقال بانکی",
  online: "آنلاین",
  investment: "سرمایه‌گذاری",
  loan: "وام",
  grant: "کمک بلاعوض",
  revenue: "درآمد",
  active: "فعال",
  completed: "تکمیل‌شده",
  on_hold: "متوقف",
  true: "بله",
  false: "خیر",
};

function displayQueryValue(value: unknown, type: string): string {
  if (value === null || value === undefined || value === "") return "—";
  if (type === "amount") return formatRials(Number(value) || 0);
  return VALUE_LABELS[String(value)] ?? String(value);
}

interface FilterRow {
  id: number;
  field: string;
  op: string;
  value: string;
}

let fId = 1;

export default function QueryBuilderPage() {
  const [dataset, setDataset] = useState("invoices");
  const [fields, setFields] = useState<string[]>(["number", "customer_name", "total", "status"]);
  const [filters, setFilters] = useState<FilterRow[]>([
    { id: fId++, field: "status", op: "eq", value: "issued" },
  ]);
  const [sorts, setSorts] = useState<{ field: string; dir: "asc" | "desc" }[]>([]);
  const [summary, setSummary] = useState("");
  const [result, setResult] = useState<Awaited<ReturnType<typeof queryBuilderApi.run>> | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [saveName, setSaveName] = useState("");
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: datasets, isLoading: datasetsLoading } = useQuery({
    queryKey: ["qb-datasets"],
    queryFn: queryBuilderApi.datasets,
  });
  const { data: templates } = useQuery({ queryKey: ["qb-templates"], queryFn: queryBuilderApi.templates });
  const { data: saved, refetch: refetchSaved } = useQuery({ queryKey: ["qb-saved"], queryFn: queryBuilderApi.saved });

  const current: QueryDataset | undefined = useMemo(
    () => datasets?.find((d) => d.id === dataset),
    [datasets, dataset],
  );

  function buildAst() {
    return {
      dataset,
      fields,
      filters: filters
        .filter((f) => f.field && f.value !== "")
        .map((f) => ({ field: f.field, op: f.op, value: f.op === "in" ? f.value.split(",").map((s) => s.trim()) : f.value })),
      sorts,
      aggregations: [],
      page,
      page_size: pageSize,
    };
  }

  async function doRun(astOverride?: object) {
    setRunError(null);
    try {
      const res = await queryBuilderApi.run(astOverride ?? buildAst());
      setResult(res);
      setPage(res.page);
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "خطای ناشناخته");
    }
  }

  async function refreshSummary() {
    try {
      const res = await queryBuilderApi.summarize(buildAst());
      setSummary(res.summary);
    } catch {
      setSummary("");
    }
  }

  useEffect(() => {
    void refreshSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, fields, filters, sorts, page, pageSize]);

  function applyTemplate(tpl: QueryTemplate) {
    const ast = tpl.ast as { dataset: string; fields: string[]; filters?: FilterRow[]; sorts?: { field: string; dir: string }[] };
    setDataset(ast.dataset);
    setFields(ast.fields ?? []);
    setFilters(
      (ast.filters ?? []).map((f) => ({
        id: fId++,
        field: String((f as { field: string }).field),
        op: String((f as { op: string }).op),
        value: String((f as { value: unknown }).value),
      })),
    );
    setSorts((ast.sorts ?? []).map((s) => ({ field: s.field, dir: s.dir as "asc" | "desc" })));
    setPage(1);
    setResult(null);
  }

  function toggleField(field: string) {
    setFields((prev) => (prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]));
  }

  const exportBusy = useMutation({
    mutationFn: (format: "csv" | "xlsx") => queryBuilderApi.exportFile(format, buildAst()),
    onMutate: () => setActionError(null),
    onError: (error) => setActionError(error instanceof Error ? error.message : "خروجی ایجاد نشد"),
  });
  const saveMutation = useMutation({
    mutationFn: () => queryBuilderApi.save(saveName, dataset, buildAst()),
    onSuccess: () => {
      setSaveMsg("ذخیره شد");
      setSaveName("");
      void refetchSaved();
      setTimeout(() => setSaveMsg(null), 3000);
    },
    onError: (e) => setSaveMsg(e instanceof Error ? e.message : "خطا"),
  });

  const totalCols = useMemo(() => result?.columns ?? [], [result]);
  const totals = useMemo(() => {
    if (!result) return null;
    const idx = totalCols.map((c, i) => (c.type === "amount" ? i : -1)).filter((i) => i >= 0);
    if (idx.length === 0) return null;
    const sums = idx.map((i) => result.rows.reduce((s, r) => s + (Number(r[i]) || 0), 0));
    return { idx, sums };
  }, [result, totalCols]);

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">پرس‌وجو و جست‌وجو</h1>
        <p className="mt-0.5 text-xs text-muted">
          بدون نیاز به دانش فنی، داده‌ها را جست‌وجو، فیلتر و خروجی بگیرید — فقط با گزینه‌های آماده
        </p>
      </div>

      {/* templates */}
      <div className="mb-3 flex flex-wrap gap-2">
        <span className="text-xs font-bold text-muted self-center">قالب‌های آماده:</span>
        {(templates ?? []).map((t) => (
          <button key={t.id} className="chip" onClick={() => applyTemplate(t)} title={t.description}>
            {t.name}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* builder */}
        <section className="card p-4 lg:col-span-1">
          <h2 className="mb-3 text-sm font-extrabold">ساخت پرس‌وجو</h2>

          <label className="label" htmlFor="qb-dataset">مجموعه داده</label>
          <select id="qb-dataset" className="input mb-3" value={dataset} onChange={(e) => { setDataset(e.target.value); setPage(1); setResult(null); }}>
            {(datasets ?? []).map((d) => (
              <option key={d.id} value={d.id}>{d.label}</option>
            ))}
          </select>

          <div className="mb-3">
            <span className="label">فیلدها</span>
            <div className="flex flex-wrap gap-1.5">
              {(current?.columns ?? []).map((c) => (
                <button
                  key={c.field}
                  className={`chip ${fields.includes(c.field) ? "active" : ""}`}
                  onClick={() => toggleField(c.field)}
                  aria-pressed={fields.includes(c.field)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-3">
            <span className="label">شرطها</span>
            {filters.map((f) => {
              const selectedColumn = current?.columns.find((column) => column.field === f.field);
              const options = selectedColumn?.type === "bool" ? ["true", "false"] : selectedColumn?.enum_options;
              return (
              <div key={f.id} className="mb-2 grid grid-cols-[1fr_auto_1fr_auto] gap-1.5 items-center">
                <select className="input !px-1.5 !py-1 text-xs" value={f.field}
                  onChange={(e) => setFilters((prev) => prev.map((x) => x.id === f.id ? { ...x, field: e.target.value, op: "eq", value: "" } : x))}>
                  {(current?.columns ?? []).map((c) => (
                    <option key={c.field} value={c.field}>{c.label}</option>
                  ))}
                </select>
                <select className="input !px-1.5 !py-1 text-xs" value={f.op}
                  onChange={(e) => setFilters((prev) => prev.map((x) => x.id === f.id ? { ...x, op: e.target.value } : x))}>
                  {Object.entries(OP_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                {options && options.length > 0 ? (
                  <select className="input !px-1.5 !py-1 text-xs" value={f.value}
                    aria-label="مقدار شرط"
                    onChange={(e) => setFilters((prev) => prev.map((x) => x.id === f.id ? { ...x, value: e.target.value } : x))}>
                    <option value="">انتخاب…</option>
                    {options.map((option) => <option key={option} value={option}>{VALUE_LABELS[option] ?? option}</option>)}
                  </select>
                ) : (
                  <input className="input !px-1.5 !py-1 text-xs" dir="ltr" value={f.value}
                    onChange={(e) => setFilters((prev) => prev.map((x) => x.id === f.id ? { ...x, value: e.target.value } : x))}
                    placeholder="مقدار" />
                )}
                <button className="icon-btn" aria-label="حذف شرط"
                  onClick={() => setFilters((prev) => prev.filter((x) => x.id !== f.id))}>
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
                </button>
              </div>
              );
            })}
            <button className="btn btn-ghost btn-sm" onClick={() => setFilters((prev) => [...prev, { id: fId++, field: current?.columns[0]?.field ?? "", op: "eq", value: "" }])}>
              + افزودن شرط
            </button>
          </div>

          <div className="mb-3">
            <span className="label">مرتب‌سازی</span>
            {sorts.map((s, i) => (
              <div key={i} className="mb-2 grid grid-cols-[1fr_auto_auto] gap-1.5 items-center">
                <select className="input !px-1.5 !py-1 text-xs" value={s.field}
                  onChange={(e) => setSorts((prev) => prev.map((x, j) => j === i ? { ...x, field: e.target.value } : x))}>
                  {(current?.columns ?? []).map((c) => (
                    <option key={c.field} value={c.field}>{c.label}</option>
                  ))}
                </select>
                <select className="input !px-1.5 !py-1 text-xs" value={s.dir}
                  onChange={(e) => setSorts((prev) => prev.map((x, j) => j === i ? { ...x, dir: e.target.value as "asc" | "desc" } : x))}>
                  <option value="asc">صعودی</option>
                  <option value="desc">نزولی</option>
                </select>
                <button className="icon-btn" aria-label="حذف مرتب‌سازی"
                  onClick={() => setSorts((prev) => prev.filter((_, j) => j !== i))}>
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
                </button>
              </div>
            ))}
            <button className="btn btn-ghost btn-sm" onClick={() => setSorts((prev) => [...prev, { field: current?.columns[0]?.field ?? "", dir: "asc" }])}>
              + افزودن مرتب‌سازی
            </button>
          </div>

          <button className="btn btn-primary w-full" onClick={() => void doRun()}>اجرای پرس‌وجو</button>
        </section>

        {/* results */}
        <section className="lg:col-span-2">
          {summary ? (
            <p className="mb-3 rounded-md bg-primary-soft px-3 py-2 text-xs leading-5 text-primary-strong">
              <b>خلاصه:</b> {summary}
            </p>
          ) : null}
          {runError ? <p className="error mb-3" role="alert">{runError}</p> : null}
          {actionError ? <p className="error mb-3" role="alert">{actionError}</p> : null}

          <div className="mb-3 flex flex-wrap items-center gap-2">
            <select className="input w-auto !py-1 text-xs" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>
              {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} در صفحه</option>)}
            </select>
            <button className="btn btn-ghost btn-sm" disabled={exportBusy.isPending || !result}
              onClick={() => exportBusy.mutate("csv")}>
              خروجی CSV
            </button>
            <button className="btn btn-ghost btn-sm" disabled={exportBusy.isPending || !result}
              onClick={() => exportBusy.mutate("xlsx")}>
              خروجی Excel
            </button>
            <span className="flex-1" />
            <input className="input w-44 !py-1 text-xs" placeholder="نام برای ذخیره…" value={saveName}
              onChange={(e) => setSaveName(e.target.value)} />
            <button className="btn btn-ghost btn-sm" disabled={!saveName.trim() || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}>
              ذخیره نما
            </button>
            {saveMsg ? <span className="text-xs font-bold text-success-strong">{saveMsg}</span> : null}
          </div>

          {saved && saved.length > 0 ? (
            <div className="mb-3 flex flex-wrap gap-2">
              {saved.map((q) => (
                <span key={q.id} className="chip">
                  {q.name}
                  <button
                    className="text-xs underline"
                    onClick={() => {
                      if (q.ast) void doRun(q.ast);
                    }}
                  >
                    اجرا
                  </button>
                  <button className="text-xs text-muted" title="حذف"
                    onClick={() => {
                      setActionError(null);
                      void queryBuilderApi.remove(q.id)
                        .then(() => refetchSaved())
                        .catch((removeError: unknown) => {
                          setActionError(removeError instanceof Error ? removeError.message : "حذف نما انجام نشد");
                        });
                    }}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          ) : null}

          {datasetsLoading ? <LoadingBlock /> : null}

          {result ? (
            <div className="card overflow-hidden">
              <div className="max-h-[560px] overflow-auto">
                <table className="w-full min-w-[720px] text-right text-sm">
                  <thead className="sticky top-0 z-10">
                    <tr className="bg-[var(--thead-bg)] text-[11px] font-extrabold text-[var(--thead-text)]">
                      <th className="px-3 py-2.5">{faDigits(result.page)}</th>
                      {totalCols.map((c) => (
                        <th key={c.field} className={`px-3 py-2.5 ${c.type === "amount" ? "text-left" : ""}`}>{c.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dashed divide-border">
                    {result.rows.map((row, ri) => (
                      <tr key={ri} className="hover:bg-[var(--row-hover)]">
                        <td className="px-3 py-2 text-xs text-muted">{faDigits((result.page - 1) * result.page_size + ri + 1)}</td>
                        {totalCols.map((c, ci) => (
                          <td key={ci} className={`px-3 py-2 ${c.type === "amount" ? "text-left font-bold tabular-nums" : ""}`}>
                            {displayQueryValue(row[ci], c.type)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                  {totals ? (
                    <tfoot>
                      <tr className="border-t-2 border-border-strong bg-surface-2 font-bold">
                        <td className="px-3 py-2 text-xs">جمع</td>
                        {totalCols.map((c, i) => (
                          <td key={i} className={`px-3 py-2 tabular-nums ${c.type === "amount" ? "text-left" : ""}`}>
                            {totals.idx.includes(i) ? formatRials(totals.sums[totals.idx.indexOf(i)] ?? 0) : ""}
                          </td>
                        ))}
                      </tr>
                    </tfoot>
                  ) : null}
                </table>
              </div>
              <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-muted">
                <span>{faDigits(result.total)} ردیف</span>
                <div className="flex items-center gap-1">
                  <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => { setPage(page - 1); void doRun({ ...buildAst(), page: page - 1 }); }}>قبلی</button>
                  <span>{faDigits(page)}</span>
                  <button className="btn btn-ghost btn-sm" disabled={!result.has_more} onClick={() => { setPage(page + 1); void doRun({ ...buildAst(), page: page + 1 }); }}>بعدی</button>
                </div>
              </div>
            </div>
          ) : null}

          {!datasetsLoading && !result ? (
            <div className="card px-4 py-10 text-center text-sm text-muted">
              یک قالب آماده انتخاب کنید یا پرس‌وجوی خود را بسازید و «اجرای پرس‌وجو» را بزنید.
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
