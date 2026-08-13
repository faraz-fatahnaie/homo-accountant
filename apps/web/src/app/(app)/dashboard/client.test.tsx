import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { role: "accountant" },
    loading: false,
    isWriter: true,
    isOwner: false,
    canDraft: true,
    refetch: vi.fn(),
    logout: vi.fn(),
  }),
}));

const state: {
  dashboard: Record<string, unknown> | undefined;
  entries: unknown[];
  isLoading: boolean;
} = { dashboard: undefined, entries: [], isLoading: false };

vi.mock("@tanstack/react-query", () => ({
  useQuery: (opts: { queryKey: string[] }) => ({
    data: opts.queryKey[0] === "entries" ? state.entries : state.dashboard,
    isLoading: state.isLoading,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import DashboardClient from "./client";

const dashboard = {
  as_of: "2026-08-13",
  fiscal_year: 1405,
  period_start: "2026-03-21",
  period_end: "2026-08-13",
  cash_bank: 401_500_000,
  receivables: 216_000_000,
  payables: 30_000_000,
  revenue: 266_000_000,
  expenses: 78_500_000,
  net_income: 187_500_000,
  cash_flow_net: 401_500_000,
  cash_flow_reconciled: true,
  receivable_aging_total: 216_000_000,
  payable_aging_total: 30_000_000,
  aging_reconciled: true,
  total_budget: 200_000_000,
  total_actual: 48_500_000,
  budget_utilization: 0.2425,
  funding_total: 150_000_000,
  funding_reconciled: true,
  recent_entries: [
    { id: 1, entry_date: "2026-08-13", reference: "J-1405-0002", memo: "هزینه مواد اولیه", total: 48_500_000 },
  ],
  key_accounts: [{ code: "102", name: "بانک — حساب جاری", type: "asset", balance: 401_500_000 }],
};

describe("dashboard client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.dashboard = undefined;
    state.entries = [];
    state.isLoading = false;
  });

  it("shows real KPIs derived from the reports endpoint", () => {
    state.dashboard = dashboard;
    render(<DashboardClient />);
    expect(screen.getByText("موجودی نقد و بانک")).toBeInTheDocument();
    expect(screen.getByText("درآمد دوره")).toBeInTheDocument();
    expect(screen.getByText("هزینههای دوره")).toBeInTheDocument();
    expect(screen.getByText("نتیجه خالص")).toBeInTheDocument();
    expect(screen.getByText("دریافتنی (مشتریان)")).toBeInTheDocument();
    // KPI cards link to their reports
    expect(screen.getByRole("link", { name: /موجودی نقد و بانک/ }).getAttribute("href")).toBe("/reports/cash-flow");
    expect(screen.getByRole("link", { name: /نتیجه خالص/ }).getAttribute("href")).toBe("/reports/profit-loss");
    // recent entry from the report
    expect(screen.getByText("هزینه مواد اولیه")).toBeInTheDocument();
    // key account drill-down to GL
    const gl = screen.getByRole("link", { name: /بانک — حساب جاری/ });
    expect(gl.getAttribute("href")).toBe("/reports/general-ledger?account_code=102");
  });

  it("shows empty state when there is no data", () => {
    state.dashboard = { ...dashboard, cash_bank: 0, revenue: 0, expenses: 0, net_income: 0, receivables: 0, payables: 0, key_accounts: [], recent_entries: [] };
    render(<DashboardClient />);
    expect(screen.getByRole("link", { name: "اولین سند را ثبت کنید" })).toBeInTheDocument();
  });
});
