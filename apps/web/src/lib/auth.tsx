"use client";

/**
 * Auth context: loads the current user once and exposes role so pages can
 * be permission-aware in the UI (real enforcement is always server-side).
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
import { authApi, clearTokens, getTokens, type UserOut } from "@/lib/api";

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
    } catch {
      clearTokens();
      router.replace("/login");
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
