import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { replace, me, logoutApi, clearLegacyTokens } = vi.hoisted(() => ({
  replace: vi.fn(),
  me: vi.fn(),
  logoutApi: vi.fn(),
  clearLegacyTokens: vi.fn(),
}));

vi.mock("next/navigation", () => {
  const router = { replace };
  return { useRouter: () => router };
});
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    authApi: { ...actual.authApi, me, logout: logoutApi },
    clearLegacyTokens,
  };
});

import { ApiError } from "./api";
import { AuthProvider, useAuth } from "./auth";

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("auth provider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the cookie session and derives role permissions", async () => {
    me.mockResolvedValue({ id: 1, full_name: "مدیر", email: "owner@example.com", role: "owner" });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user?.email).toBe("owner@example.com");
    expect(result.current.isOwner).toBe(true);
    expect(result.current.isWriter).toBe(true);
    expect(clearLegacyTokens).toHaveBeenCalled();
  });

  it("redirects only when the server definitively rejects the session", async () => {
    me.mockRejectedValue(new ApiError(401, { error: { code: "auth_error", message: "نشست نامعتبر" } }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(replace).toHaveBeenCalledWith("/login");
    expect(me).toHaveBeenCalledTimes(1);
  });

  it("retries a transient failure without logging the user out", async () => {
    me.mockRejectedValueOnce(new Error("network")).mockResolvedValue({
      id: 2,
      full_name: "حسابدار",
      email: "accountant@example.com",
      role: "accountant",
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false), { timeout: 2000 });
    expect(result.current.user?.role).toBe("accountant");
    expect(replace).not.toHaveBeenCalled();
    expect(me).toHaveBeenCalledTimes(2);
  });

  it("revokes the server session and redirects on logout", async () => {
    me.mockResolvedValue({ id: 3, full_name: "کاربر", email: "staff@example.com", role: "staff" });
    logoutApi.mockResolvedValue(undefined);
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.logout());
    expect(logoutApi).toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith("/login");
  });
});
