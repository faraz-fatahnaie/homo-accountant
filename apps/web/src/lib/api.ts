/**
 * Typed API client for the Homo Accountant API.
 *
 * Slice 1: hand-written fetch wrapper around the OpenAPI contract. From slice 2
 * onwards this file is replaced by the generated client in packages/api-client
 * (openapi-typescript) to prevent contract drift; the wrapper's shape stays the same.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const TOKEN_KEY = "homo-accountant-access-token";
export const REFRESH_KEY = "homo-accountant-refresh-token";

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

export function getTokens(): { access: string | null; refresh: string | null } {
  try {
    return {
      access: window.localStorage.getItem(TOKEN_KEY),
      refresh: window.localStorage.getItem(REFRESH_KEY),
    };
  } catch {
    return { access: null, refresh: null };
  }
}

export function storeTokens(access: string, refresh: string) {
  try {
    window.localStorage.setItem(TOKEN_KEY, access);
    window.localStorage.setItem(REFRESH_KEY, refresh);
  } catch {
    /* private mode */
  }
}

export function clearTokens() {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
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
  if (auth) {
    const { access } = getTokens();
    if (access) requestHeaders.Authorization = `Bearer ${access}`;
  }

  const init: RequestInit = { method, headers: requestHeaders, credentials: "omit" };
  if (body !== undefined) {
    init.body = isFormData ? (body as FormData) : JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE}${path}`, init);

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

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
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
    api<TokenPair>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  logout: (refresh_token: string) =>
    api<{ status: string }>("/auth/logout", { method: "POST", auth: false, body: { refresh_token } }),
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
  vendor: "تأمینکننده",
  employee: "کارمند",
  investor: "سرمایهگذار",
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
  completed: "تکمیلشده",
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
  draft: "پیشنویس",
  issued: "صادرشده",
  partially_paid: "جزیی پرداختشده",
  paid: "پرداختشده",
  void: "باطلشده",
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
  draft: "پیشنویس",
  open: "باز (ثبتشده)",
  partially_paid: "جزیی پرداختشده",
  paid: "پرداختشده",
  void: "باطلشده",
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
    const { access } = getTokens();
    const response = await fetch(`${API_BASE}/invoices/${id}/pdf`, {
      headers: access ? { Authorization: `Bearer ${access}` } : {},
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
