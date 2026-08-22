import { describe, expect, it, vi, beforeEach } from "vitest";
import { ApiError, API_BASE, authApi } from "./api";

describe("api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("joins base URL and path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await authApi.me();
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/users/me`, expect.any(Object));
  });

  it("uses cookie credentials and never reads a legacy bearer token", async () => {
    window.localStorage.setItem("homo-accountant-access-token", "tok-123");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await authApi.me();
    const opts = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = opts.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    expect(opts.credentials).toBe("include");
  });

  it("parses the API error envelope", async () => {
    const body = { error: { code: "invalid_credentials", message: "ایمیل یا رمز عبور نادرست است" } };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(body), { status: 401, headers: { "Content-Type": "application/json" } }),
      ),
    );
    try {
      await authApi.login("a@example.com", "x");
      expect.unreachable("should throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(401);
      expect(apiErr.code).toBe("invalid_credentials");
      expect(apiErr.message).toBe("ایمیل یا رمز عبور نادرست است");
    }
  });

  it("does not send auth header for login", async () => {
    window.localStorage.setItem("homo-accountant-access-token", "tok-123");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ expires_in: 1800 }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await authApi.login("a@example.com", "password-1");
    const opts = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((opts.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("refreshes an expired cookie session once and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ expires_in: 1800 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 1 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await authApi.me();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE}/auth/refresh`,
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
