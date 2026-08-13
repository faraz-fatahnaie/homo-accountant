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

export const authApi = {
  login: (email: string, password: string) =>
    api<TokenPair>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  logout: (refresh_token: string) =>
    api<{ status: string }>("/auth/logout", { method: "POST", auth: false, body: { refresh_token } }),
  me: () => api<UserOut>("/users/me"),
};
