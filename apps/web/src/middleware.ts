import { NextResponse } from "next/server";

/**
 * CSP delivered per-request via middleware (verified in slice 9 with a real
 * browser). Notes:
 * - `script-src` includes 'unsafe-inline' because Next.js App Router pages
 *   are statically prerendered with inline RSC bootstrap scripts; per-request
 *   nonces cannot be applied to cached static HTML (verified empirically).
 *   All other directives stay strict.
 * - Static pages still receive the CSP header (middleware headers are applied
 *   per request) — only the inline-script nonce trick is unavailable.
 */
// If NEXT_PUBLIC_API_URL is an absolute origin (e.g. dev points at
// http://localhost:8000) it must be allowed by connect-src; a RELATIVE path
// (production: /api/v1 through nginx) means same-origin, so 'self' covers it.
const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
const API_ORIGIN = RAW_API_URL.startsWith("http") ? RAW_API_URL : "";
const RAW_SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN ?? "";
let SENTRY_ORIGIN = "";
try {
  SENTRY_ORIGIN = RAW_SENTRY_DSN ? new URL(RAW_SENTRY_DSN).origin : "";
} catch {
  // Invalid DSNs are ignored; Sentry remains disabled.
}

export function middleware() {
  const response = NextResponse.next();

  if (process.env.NODE_ENV === "production") {
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'", // Next.js RSC inline bootstrap (static prerender)
      "style-src 'self' 'unsafe-inline'", // Tailwind/Next inline styles
      `connect-src 'self'${API_ORIGIN ? ` ${API_ORIGIN}` : ""}${SENTRY_ORIGIN ? ` ${SENTRY_ORIGIN}` : ""}`,
      "img-src 'self' data:",
      "font-src 'self'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join("; ");
    response.headers.set("Content-Security-Policy", csp);
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api|docs|openapi.json).*)"],
};
