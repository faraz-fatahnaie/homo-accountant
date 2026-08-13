import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { TrialBalanceReport } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/reports/trial-balance",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { role: "viewer" },
    loading: false,
    isWriter: false,
    isOwner: false,
    canDraft: false,
    refetch: vi.fn(),
    logout: vi.fn(),
  }),
}));

const state: {
  data: TrialBalanceReport | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} = { data: undefined, isLoading: false, isError: false, error: null };

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: state.data,
    isLoading: state.isLoading,
    isError: state.isError,
    error: state.error,
    refetch: vi.fn(),
  }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import TrialBalancePage from "./page";

const report: TrialBalanceReport = {
  as_of: "2026-08-13",
  rows: [
    { code: "102", name: "بانک — حساب جاری", type: "asset", debit_total: 450_000_000, credit_total: 48_500_000, balance: 401_500_000 },
    { code: "603", name: "مواد اولیه و کالا", type: "expense", debit_total: 48_500_000, credit_total: 0, balance: 48_500_000 },
  ],
  total_debit: 498_500_000,
  total_credit: 498_500_000,
  balanced: true,
  reconciled: true,
};

describe("trial balance page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.data = undefined;
    state.isLoading = false;
    state.isError = false;
    state.error = null;
  });

  it("shows accounts grouped by type with signed balances", () => {
    state.data = report;
    render(<TrialBalancePage />);
    expect(screen.getAllByText("تراز آزمایشی").length).toBeGreaterThan(0);
    expect(screen.getByText("دارایی")).toBeInTheDocument();
    expect(screen.getByText("هزینه")).toBeInTheDocument();
    expect(screen.getByText("بانک — حساب جاری")).toBeInTheDocument();
    expect(screen.getByText("مواد اولیه و کالا")).toBeInTheDocument();
    // totals row (Persian digits)
    expect(screen.getByText("جمع بدهکار")).toBeInTheDocument();
    expect(screen.getByText("جمع بستانکار")).toBeInTheDocument();
    // reconciled badge
    expect(screen.getByText("تراز است")).toBeInTheDocument();
  });

  it("flags an unbalanced trial balance", () => {
    state.data = { ...report, balanced: false, reconciled: false };
    render(<TrialBalancePage />);
    expect(screen.getByText("تراز نیست")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    state.isLoading = true;
    render(<TrialBalancePage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
