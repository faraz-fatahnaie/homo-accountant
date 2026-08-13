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
  if (body !== undefined) requestHeaders["Content-Type"] = "application/json";
  if (auth) {
    const { access } = getTokens();
    if (access) requestHeaders.Authorization = `Bearer ${access}`;
  }

  const init: RequestInit = { method, headers: requestHeaders, credentials: "omit" };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
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
