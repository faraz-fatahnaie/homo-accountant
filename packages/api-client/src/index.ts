/**
 * Homo Accountant — typed API client generated from the FastAPI OpenAPI
 * contract. `schema.d.ts` is the machine-readable contract snapshot (drift
 * is checked in CI); the app currently uses the hand-written wrapper in
 * apps/web/src/lib/api.ts with the same shapes.
 *
 * Regenerate:  npm run generate   (requires the API running on :8000)
 * Check drift: npm run typecheck  + git diff --exit-code src/schema.d.ts
 */
import type { components, operations, paths } from "./schema";

export type { components, operations, paths } from "./schema";

/** OpenAPI-generated request/response types (component schemas). */
export type ApiComponents = components["schemas"];

/** Typed API operation paths (e.g. "/api/v1/accounts"). */
export type ApiPaths = paths;

/** Operation types keyed by operationId (e.g. accounts_balances). */
export type ApiOperations = operations;

/** Minimal typed fetch wrapper around the generated paths. */
export async function apiRequest<T>(
  base: string,
  path: string,
  options: { method?: string; body?: unknown; token?: string } = {},
): Promise<T> {
  const { method = "GET", body, token } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(`API ${method} ${path} -> ${response.status}`);
  return (await response.json()) as T;
}
