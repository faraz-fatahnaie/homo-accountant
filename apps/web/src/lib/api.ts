/**
 * Typed API client for the Homo Accountant API.
 *
 * Slice 1: hand-written fetch wrapper around the OpenAPI contract. From slice 2
 * onwards this file is replaced by the generated client in packages/api-client
 * (openapi-typescript) to prevent contract drift; the wrapper's shape stays the same.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const LEGACY_TOKEN_KEYS = [
  "homo-accountant-access-token",
  "homo-accountant-refresh-token",
] as const;

export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, string> | null };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, string> | null;

  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.error?.message ?? "خطای ناشناخته");
    this.name = "ApiError";
    this.status = status;
    this.code = body?.error?.code ?? "unknown";
    this.details = body?.error?.details ?? null;
  }
}

export function clearLegacyTokens() {
  try {
    for (const key of LEGACY_TOKEN_KEYS) window.localStorage.removeItem(key);
  } catch {
    /* private mode */
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  headers?: Record<string, string>;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, headers } = options;
  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isFormData) requestHeaders["Content-Type"] = "application/json";
  const init: RequestInit = { method, headers: requestHeaders, credentials: "include" };
  if (body !== undefined) {
    init.body = isFormData ? (body as FormData) : JSON.stringify(body);
  }
  let response = await fetch(`${API_BASE}${path}`, init);
  if (auth && response.status === 401 && !path.startsWith("/auth/")) {
    const refreshed = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { Accept: "application/json" },
      credentials: "include",
    });
    if (refreshed.ok) response = await fetch(`${API_BASE}${path}`, init);
  }

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, (payload as ApiErrorBody) ?? null);
  }
  return payload as T;
}

export interface SessionOut {
  expires_in: number;
}

export interface UserOut {
  id: number;
  email: string;
  full_name: string;
  role: "owner" | "accountant" | "staff" | "viewer";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";

export interface AccountOut {
  id: number;
  code: string;
  name: string;
  type: AccountType;
  parent_id: number | null;
  is_active: boolean;
  is_system: boolean;
}

export interface AccountBalanceOut {
  code: string;
  name: string;
  type: AccountType;
  debit_total: number;
  credit_total: number;
  balance: number;
}

export interface JournalLineOut {
  id: number;
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
}

export type JournalStatus = "draft" | "posted";

export interface JournalEntryOut {
  id: number;
  entry_date: string;
  reference: string | null;
  memo: string;
  status: JournalStatus;
  reversal_of_id: number | null;
  created_at: string;
  posted_at: string | null;
  lines: JournalLineOut[];
}

export interface PeriodOut {
  id: number;
  year: number;
  month: number;
  status: "open" | "closed";
  closed_at: string | null;
  reopened_at: string | null;
}

function queryString(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const authApi = {
  login: (email: string, password: string) =>
    api<SessionOut>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  logout: () => api<{ status: string }>("/auth/logout", { method: "POST", auth: false }),
  me: () => api<UserOut>("/users/me"),
};

export const accountsApi = {
  list: () => api<AccountOut[]>("/accounts"),
  create: (body: { code: string; name: string; type: AccountType; parent_code?: string }) =>
    api<AccountOut>("/accounts", { method: "POST", body }),
  balances: () => api<AccountBalanceOut[]>("/accounts/balances"),
};

/* ---------------- contacts ---------------- */

export interface ContactOut {
  id: number;
  name: string;
  roles: string[];
  phone: string | null;
  email: string | null;
  national_id: string | null;
  address: string | null;
  payment_terms_days: number;
  notes: string | null;
  is_active: boolean;
  created_at: string;
}

export type ContactRole =
  | "customer" | "vendor" | "employee" | "investor" | "lender" | "grantor" | "other";

export const CONTACT_ROLE_LABELS: Record<ContactRole, string> = {
  customer: "مشتری",
  vendor: "تأمین‌کننده",
  employee: "کارمند",
  investor: "سرمایه‌گذار",
  lender: "وامدهنده (بانک)",
  grantor: "کمککننده",
  other: "سایر",
};

export const contactsApi = {
  list: (activeOnly = false) =>
    api<ContactOut[]>(`/contacts${activeOnly ? "?active_only=true" : ""}`),
  create: (body: Partial<ContactOut>) => api<ContactOut>("/contacts", { method: "POST", body }),
};

/* ---------------- projects ---------------- */

export type ProjectStatus = "active" | "completed" | "on_hold";

export interface ProjectOut {
  id: number;
  name: string;
  status: ProjectStatus;
  description: string | null;
  responsible_person: string | null;
  start_date: string | null;
  end_date: string | null;
  budget: number;
  created_at: string;
}

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  active: "فعال",
  completed: "تکمیل‌شده",
  on_hold: "معلق",
};

export const projectsApi = {
  list: (activeOnly = false) =>
    api<ProjectOut[]>(`/projects${activeOnly ? "?active_only=true" : ""}`),
  create: (body: Partial<ProjectOut>) => api<ProjectOut>("/projects", { method: "POST", body }),
};

/* ---------------- expenses ---------------- */

export type PaymentMethod = "cash" | "bank" | "online";
export type ExpenseStatus = "draft" | "posted" | "voided";

export interface AttachmentOut {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface ExpenseOut {
  id: number;
  number: string | null;
  entry_date: string;
  contact_id: number | null;
  project_id: number | null;
  account_code: string;
  account_name: string;
  amount: number;
  payment_method: PaymentMethod;
  reference: string | null;
  description: string;
  notes: string | null;
  status: ExpenseStatus;
  journal_entry_id: number | null;
  created_at: string;
  posted_at: string | null;
  attachments: AttachmentOut[];
}

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: "نقدی",
  bank: "انتقال بانکی",
  online: "درگاه آنلاین",
};

export const expensesApi = {
  list: () => api<ExpenseOut[]>("/expenses"),
  detail: (id: number) => api<ExpenseOut>(`/expenses/${id}`),
  create: (body: object) => api<ExpenseOut>("/expenses", { method: "POST", body }),
  post: (id: number) => api<ExpenseOut>(`/expenses/${id}/post`, { method: "POST" }),
  voidEntry: (id: number) => api<ExpenseOut>(`/expenses/${id}/void`, { method: "POST" }),
  uploadAttachment: (expenseId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<AttachmentOut>(`/expenses/${expenseId}/attachments`, {
      method: "POST",
      auth: true,
      body: form,
    });
  },
};

/* ---------------- invoices ---------------- */

export type InvoiceStatus = "draft" | "issued" | "partially_paid" | "paid" | "void";

export interface InvoiceItemOut {
  id: number;
  description: string;
  quantity: number;
  unit_price: number;
  discount: number;
  line_total: number;
}

export interface InvoicePaymentOut {
  id: number;
  amount: number;
  paid_at: string;
  method: PaymentMethod;
  reference: string | null;
  journal_entry_id: number | null;
  created_at: string;
}

export interface InvoiceOut {
  id: number;
  number: string | null;
  customer_id: number;
  customer_name: string;
  project_id: number | null;
  issue_date: string;
  due_date: string;
  status: InvoiceStatus;
  notes: string | null;
  payment_instructions: string | null;
  total: number;
  paid_total: number;
  balance: number;
  is_overdue: boolean;
  journal_entry_id: number | null;
  created_at: string;
  items: InvoiceItemOut[];
  payments: InvoicePaymentOut[];
}

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "پیش‌نویس",
  issued: "صادرشده",
  partially_paid: "جزئی پرداخت‌شده",
  paid: "پرداخت‌شده",
  void: "باطل‌شده",
};

/* ---------------- bills (payables) ---------------- */

export type BillStatus = "draft" | "open" | "partially_paid" | "paid" | "void";

export interface BillPaymentOut {
  id: number;
  amount: number;
  paid_at: string;
  method: PaymentMethod;
  reference: string | null;
  journal_entry_id: number | null;
  created_at: string;
}

export interface BillOut {
  id: number;
  number: string | null;
  vendor_id: number;
  vendor_name: string;
  project_id: number | null;
  account_code: string;
  account_name: string;
  issue_date: string;
  due_date: string;
  bill_number: string | null;
  status: BillStatus;
  memo: string;
  total: number;
  paid_total: number;
  balance: number;
  is_overdue: boolean;
  journal_entry_id: number | null;
  created_at: string;
  payments: BillPaymentOut[];
}

export const BILL_STATUS_LABELS: Record<BillStatus, string> = {
  draft: "پیش‌نویس",
  open: "باز (ثبت‌شده)",
  partially_paid: "جزئی پرداخت‌شده",
  paid: "پرداخت‌شده",
  void: "باطل‌شده",
};

export const billsApi = {
  list: () => api<BillOut[]>("/bills"),
  detail: (id: number) => api<BillOut>(`/bills/${id}`),
  create: (body: object) => api<BillOut>("/bills", { method: "POST", body }),
  post: (id: number) => api<BillOut>(`/bills/${id}/post`, { method: "POST" }),
  pay: (id: number, body: { amount: number; paid_at: string; method: PaymentMethod; reference?: string }) =>
    api<BillPaymentOut>(`/bills/${id}/payments`, { method: "POST", body }),
  voidEntry: (id: number) => api<BillOut>(`/bills/${id}/void`, { method: "POST" }),
};

/* ---------------- funding ---------------- */

export type FundingType = "investment" | "loan" | "grant" | "revenue";

export interface FundingEventOut {
  id: number;
  number: string | null;
  funding_type: FundingType;
  contact_id: number | null;
  contact_name: string;
  project_id: number | null;
  event_date: string;
  amount: number;
  method: PaymentMethod;
  agreement_ref: string | null;
  maturity_date: string | null;
  notes: string | null;
  status: string;
  journal_entry_id: number | null;
  created_at: string;
}

export const FUNDING_TYPE_LABELS: Record<FundingType, string> = {
  investment: "سرمایه‌گذاری",
  loan: "وام",
  grant: "کمک بلاعوض",
  revenue: "درآمد",
};

export interface FundingMappingOut {
  funding_type: FundingType;
  account_code: string;
}

export const fundingApi = {
  list: () => api<FundingEventOut[]>("/funding"),
  create: (body: object) => api<FundingEventOut>("/funding", { method: "POST", body }),
  mappings: () => api<FundingMappingOut[]>("/funding/mappings"),
  updateMapping: (fundingType: FundingType, accountCode: string) =>
    api<FundingMappingOut>(`/funding/mappings/${fundingType}`, { method: "PUT", body: { account_code: accountCode } }),
};

/* ---------------- query builder ---------------- */

export interface QueryColumnMeta {
  field: string;
  label: string;
  type: "string" | "date" | "amount" | "enum" | "bool";
  enum_options?: string[];
  amount?: boolean;
}

export interface QueryDataset {
  id: string;
  label: string;
  columns: QueryColumnMeta[];
}

export interface QueryTemplate {
  id: string;
  name: string;
  description: string;
  ast: object;
}

export interface QueryResult {
  columns: QueryColumnMeta[];
  rows: unknown[][];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  aggregated: boolean;
}

export interface SavedQueryOut {
  id: number;
  name: string;
  dataset: string;
  ast?: object;
  summary: string;
  created_at: string;
}

export const queryBuilderApi = {
  datasets: () => api<QueryDataset[]>("/query-builder/datasets"),
  templates: () => api<QueryTemplate[]>("/query-builder/templates"),
  run: (ast: object) => api<QueryResult>("/query-builder/run", { method: "POST", body: ast }),
  summarize: (ast: object) => api<{ summary: string }>("/query-builder/summarize", { method: "POST", body: ast }),
  saved: () => api<SavedQueryOut[]>("/query-builder/saved"),
  save: (name: string, dataset: string, ast: object) =>
    api<{ id: number; name: string }>("/query-builder/saved", { method: "POST", body: { name, dataset, ast } }),
  duplicate: (id: number) =>
    api<{ id: number; name: string }>(`/query-builder/saved/${id}/duplicate`, { method: "POST" }),
  remove: (id: number) => api<null>(`/query-builder/saved/${id}`, { method: "DELETE" }),
  async exportFile(format: "csv" | "xlsx", ast: object, filename = `query.${format}`) {
    const response = await fetch(`${API_BASE}/query-builder/export?format=${format}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(ast),
    });
    if (!response.ok) throw new ApiError(response.status, null);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  },
};

export const invoicesApi = {
  list: () => api<InvoiceOut[]>("/invoices"),
  detail: (id: number) => api<InvoiceOut>(`/invoices/${id}`),
  create: (body: object) => api<InvoiceOut>("/invoices", { method: "POST", body }),
  issue: (id: number) => api<InvoiceOut>(`/invoices/${id}/issue`, { method: "POST" }),
  pay: (id: number, body: { amount: number; paid_at: string; method: PaymentMethod; reference?: string }) =>
    api<InvoicePaymentOut>(`/invoices/${id}/payments`, { method: "POST", body }),
  voidEntry: (id: number) => api<InvoiceOut>(`/invoices/${id}/void`, { method: "POST" }),
  /** Download the PDF via an authenticated fetch → blob (a plain <a href>
   *  cannot carry the Authorization header). */
  async downloadPdf(id: number, fallbackName = `invoice-${id}.pdf`) {
    const response = await fetch(`${API_BASE}/invoices/${id}/pdf`, {
      credentials: "include",
    });
    if (!response.ok) throw new ApiError(response.status, null);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fallbackName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  },
};

export const entriesApi = {
  list: (params?: { period_year?: number; period_month?: number }) =>
    api<JournalEntryOut[]>(`/journal-entries${queryString(params ?? {})}`),
  detail: (id: number) => api<JournalEntryOut>(`/journal-entries/${id}`),
  create: (body: {
    entry_date: string;
    memo: string;
    lines: { account_code: string; debit: number; credit: number }[];
    idempotency_key?: string;
  }) => api<JournalEntryOut>("/journal-entries", { method: "POST", body }),
  post: (id: number) => api<JournalEntryOut>(`/journal-entries/${id}/post`, { method: "POST" }),
  voidEntry: (id: number) => api<JournalEntryOut>(`/journal-entries/${id}/void`, { method: "POST" }),
};

export const periodsApi = {
  list: () => api<PeriodOut[]>("/periods"),
  close: (id: number) => api<PeriodOut>(`/periods/${id}/close`, { method: "POST" }),
  reopen: (id: number) => api<PeriodOut>(`/periods/${id}/reopen`, { method: "POST" }),
};

/* ---------------- reports (slice 8) ---------------- */

export interface TrialBalanceRow {
  code: string;
  name: string;
  type: AccountType;
  debit_total: number;
  credit_total: number;
  balance: number;
}

export interface TrialBalanceReport {
  as_of: string;
  rows: TrialBalanceRow[];
  total_debit: number;
  total_credit: number;
  balanced: boolean;
  reconciled: boolean;
}

export interface SheetLine {
  code: string;
  name: string;
  amount: number;
}

export interface BalanceSheetReport {
  as_of: string;
  assets: SheetLine[];
  liabilities: SheetLine[];
  equity: SheetLine[];
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  total_liabilities_equity: number;
  net_income: number;
  reconciled: boolean;
}

export interface ProfitLossLine {
  code: string;
  name: string;
  amount: number;
  type: "revenue" | "expense";
}

export interface ProfitLossReport {
  from: string;
  to: string;
  revenue: ProfitLossLine[];
  expenses: ProfitLossLine[];
  total_revenue: number;
  total_expenses: number;
  net_income: number;
  reconciled: boolean;
}

export interface CashFlowItem {
  entry_id: number;
  date: string;
  reference: string | null;
  memo: string;
  counterparts: { code: string; name: string; type: string }[];
  inflow: number;
  outflow: number;
  net: number;
}

export interface CashFlowSection {
  items: CashFlowItem[];
  inflow: number;
  outflow: number;
  net: number;
}

export interface CashFlowReport {
  from: string;
  to: string;
  beginning_cash_bank: number;
  ending_cash_bank: number;
  net_change: number;
  sections: Record<"operating" | "financing" | "investing" | "other", CashFlowSection>;
  total_net: number;
  reconciled: boolean;
}

export interface GeneralLedgerLine {
  entry_id: number;
  date: string;
  reference: string | null;
  memo: string;
  debit: number;
  credit: number;
  balance: number;
}

export interface GeneralLedgerReport {
  account: { code: string; name: string; type: AccountType };
  from: string;
  to: string;
  opening_balance: number;
  closing_balance: number;
  lines: GeneralLedgerLine[];
  reconciled: boolean;
}

export interface AgingRow {
  number: string | null;
  contact_name: string;
  due_date: string;
  total: number;
  paid: number;
  balance: number;
  bucket: "current" | "1_30" | "31_60" | "61_90" | "over_90";
}

export interface AgingSide {
  rows: AgingRow[];
  buckets: { key: string; label: string; amount: number }[];
  total: number;
  ledger_balance: number;
  reconciled: boolean;
}

export interface AgingReport {
  as_of: string;
  receivable: AgingSide;
  payable: AgingSide;
  reconciled: boolean;
}

export interface BudgetRow {
  project_id: number;
  name: string;
  status: "active" | "completed" | "on_hold";
  budget: number;
  actual: number;
  remaining: number;
  utilization: number | null;
}

export interface BudgetVsActualReport {
  from: string;
  to: string;
  rows: BudgetRow[];
  total_budget: number;
  total_actual: number;
  total_remaining: number;
  total_utilization: number | null;
  reconciled: boolean;
}

export interface FundingTypeSummary {
  funding_type: FundingType;
  count: number;
  total: number;
  account_code: string;
  ledger_credit: number;
  reconciled: boolean;
  maturity_date: string | null;
}

export interface FundingSummaryReport {
  from: string;
  to: string;
  types: FundingTypeSummary[];
  total: number;
  reconciled: boolean;
}

export interface ReconciliationCheck {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
}

export interface ReconciliationReport {
  as_of: string;
  checks: ReconciliationCheck[];
  all_ok: boolean;
}

export interface DashboardSummary {
  as_of: string;
  fiscal_year: number;
  period_start: string;
  period_end: string;
  cash_bank: number;
  receivables: number;
  payables: number;
  revenue: number;
  expenses: number;
  net_income: number;
  cash_flow_net: number;
  cash_flow_reconciled: boolean;
  receivable_aging_total: number;
  payable_aging_total: number;
  aging_reconciled: boolean;
  total_budget: number;
  total_actual: number;
  budget_utilization: number | null;
  funding_total: number;
  funding_reconciled: boolean;
  recent_entries: { id: number; entry_date: string; reference: string | null; memo: string; total: number }[];
  key_accounts: { code: string; name: string; type: AccountType; balance: number }[];
}

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export const reportsApi = {
  dashboard: () => api<DashboardSummary>("/reports/dashboard"),
  trialBalance: (asOf?: Date) =>
    api<TrialBalanceReport>(`/reports/trial-balance${asOf ? `?as_of=${iso(asOf)}` : ""}`),
  balanceSheet: (asOf?: Date) =>
    api<BalanceSheetReport>(`/reports/balance-sheet${asOf ? `?as_of=${iso(asOf)}` : ""}`),
  profitLoss: (from: Date, to: Date) =>
    api<ProfitLossReport>(`/reports/profit-loss?from=${iso(from)}&to=${iso(to)}`),
  cashFlow: (from: Date, to: Date) =>
    api<CashFlowReport>(`/reports/cash-flow?from=${iso(from)}&to=${iso(to)}`),
  generalLedger: (accountCode: string, from: Date, to: Date) =>
    api<GeneralLedgerReport>(
      `/reports/general-ledger?account_code=${encodeURIComponent(accountCode)}&from=${iso(from)}&to=${iso(to)}`,
    ),
  aging: (asOf?: Date) => api<AgingReport>(`/reports/aging${asOf ? `?as_of=${iso(asOf)}` : ""}`),
  budgetVsActual: (from: Date, to: Date) =>
    api<BudgetVsActualReport>(`/reports/budget-vs-actual?from=${iso(from)}&to=${iso(to)}`),
  fundingSummary: (from: Date, to: Date) =>
    api<FundingSummaryReport>(`/reports/funding-summary?from=${iso(from)}&to=${iso(to)}`),
  reconciliation: (asOf?: Date) =>
    api<ReconciliationReport>(`/reports/reconciliation${asOf ? `?as_of=${iso(asOf)}` : ""}`),
};
