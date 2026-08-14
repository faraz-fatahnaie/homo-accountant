"use client";

/**
 * Auth context: loads the current user once and exposes role so pages can
 * be permission-aware in the UI (real enforcement is always server-side).
 *
 * Session-resilience rule (hardened in slice 9): a transient failure of the
 * `me()` check — a fetch aborted by navigation, a network blip, or a 5xx —
 * must NOT log the user out. Only a definitive 401 means the token is truly
 * invalid. Without this, a full-page navigation that aborts the in-flight
 * `me()` fetch would wipe the tokens and bounce the user to /login.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { ApiError, authApi, clearTokens, getTokens, type UserOut } from "@/lib/api";

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  isWriter: boolean; // accountant or owner (can post/close)
  isOwner: boolean;
  canDraft: boolean; // owner | accountant | staff (can create expense drafts)
  refetch: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 400;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!getTokens().access) {
      router.replace("/login");
      return;
    }
    try {
      const me = await authApi.me();
      setUser(me);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : undefined;
      if (status === 401) {
        // The token is genuinely rejected → real session loss.
        clearTokens();
        router.replace("/login");
        return;
      }
      // Transient failure (aborted fetch on navigation, network blip, 5xx).
      // Retry a couple of times before giving up — never clear the session
      // on a transient error.
      let lastError: unknown = err;
      for (let attempt = 0; attempt < MAX_RETRIES; attempt += 1) {
        await sleep(RETRY_DELAY_MS * (attempt + 1));
        try {
          const me = await authApi.me();
          setUser(me);
          return;
        } catch (retryErr) {
          const retryStatus = retryErr instanceof ApiError ? retryErr.status : undefined;
          if (retryStatus === 401) {
            clearTokens();
            router.replace("/login");
            return;
          }
          lastError = retryErr;
        }
      }
      // Still down — render without user data; the next full load retries.
      setUser(null);
      void lastError;
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  const logout = useCallback(() => {
    const { refresh } = getTokens();
    if (refresh) void authApi.logout(refresh).catch(() => undefined);
    clearTokens();
    router.replace("/login");
  }, [router]);

  const value: AuthState = {
    user,
    loading,
    isWriter: user?.role === "owner" || user?.role === "accountant",
    isOwner: user?.role === "owner",
    canDraft:
      user?.role === "owner" || user?.role === "accountant" || user?.role === "staff",
    refetch: load,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
