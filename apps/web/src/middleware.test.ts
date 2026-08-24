import { afterEach, describe, expect, it, vi } from "vitest";

describe("middleware CSP", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("allows the API client's default localhost origin", async () => {
    vi.stubEnv("NODE_ENV", "production");
    delete process.env.NEXT_PUBLIC_API_URL;

    const { middleware } = await import("./middleware");
    const csp = middleware().headers.get("Content-Security-Policy");

    expect(csp).toContain("connect-src 'self' http://localhost:8000");
    expect(csp).not.toContain("http://localhost:8000/api/v1");
  });
});
